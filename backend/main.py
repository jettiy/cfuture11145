from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os

# 로컬 개발 시 backend/.env 자동 로드 (파일이 있을 때만). 운영은 Cloudflare Secrets 등으로 주입.
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_env_path):
    from dotenv import load_dotenv
    load_dotenv(_env_path)

from app.database import engine, Base
from app.migrations import run_sqlite_migrations, run_postgres_rls
from app.routers import auth, users, chat, news, signals, admin, pro, support, indicators, calendar, cron, custom_events, ai, indexes
from app.websocket import router as websocket_router
from app.scheduler import start_scheduler, shutdown_scheduler
import asyncio
from sqlalchemy.exc import IntegrityError

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup (테이블 미생성 시 /api/calendar/board 등이 빈 배열 반환할 수 있음)
    try:
        Base.metadata.create_all(bind=engine)
        # NOTE: Windows 기본 콘솔(cp949)에서는 ✓/✗ 같은 문자가 UnicodeEncodeError를 유발할 수 있어 ASCII로 출력합니다.
        print("[OK] Database tables created successfully (Base.metadata.create_all executed)")
        if engine.dialect.name == "sqlite":
            run_sqlite_migrations(engine)
        run_postgres_rls(engine)
    except Exception as e:
        print(f"[ERROR] Database initialization error: {e}")
        import traceback
        traceback.print_exc()

    # Render 운영 DB 등: channels 테이블에 기본 채널(id=1)이 없으면 생성 (FK 오류 방지)
    try:
        from app.database import SessionLocal
        from app.models import Channel
        db = SessionLocal()
        try:
            ch = db.query(Channel).filter(Channel.id == 1).first()
            if not ch:
                db.add(Channel(id=1, name="Global", symbol=None))
                try:
                    db.commit()
                    print("[SEED] Created default channel id=1 (Global)")
                except IntegrityError:
                    # 동시 부팅/중복 실행 등으로 이미 생겼다면 무시
                    db.rollback()
                    print("[SEED] Default channel id=1 already exists (race)")
            else:
                print("[SEED] Default channel id=1 exists")
        finally:
            db.close()
    except Exception as e:
        print(f"[SEED] Default channel seed error (server continues): {e}")
        import traceback
        traceback.print_exc()

    # Render 등 Shell 없이 관리자 승격: ADMIN_BOOTSTRAP_USERNAME 설정 시 해당 계정을 ADMIN으로
    bootstrap_username = os.getenv("ADMIN_BOOTSTRAP_USERNAME", "").strip()
    if bootstrap_username:
        try:
            from app.database import SessionLocal
            from app.models import User, UserRole
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == bootstrap_username).first()
                if user:
                    if user.role != UserRole.ADMIN:
                        user.role = UserRole.ADMIN
                        db.commit()
                        print(f"[ADMIN_BOOTSTRAP] Promoted user to ADMIN: {bootstrap_username}")
                    else:
                        print(f"[ADMIN_BOOTSTRAP] User already ADMIN: {bootstrap_username}")
                else:
                    print(f"[ADMIN_BOOTSTRAP] User not found (no change): {bootstrap_username}")
            finally:
                db.close()
        except Exception as e:
            print(f"[ADMIN_BOOTSTRAP] Error: {e}")
            import traceback
            traceback.print_exc()
    
    # DeepSeek API 키 검증 (비동기이므로 별도 태스크로 실행)
    try:
        from app.services.llm_api_validator import validate_api_key_format
        llm_api_key = os.getenv("LLM_API_KEY", "")
        if llm_api_key:
            is_valid_format, format_error = validate_api_key_format(llm_api_key)
            if not is_valid_format:
                print(f"[WARNING] DeepSeek API 키 형식 오류: {format_error}")
            else:
                print("[INFO] DeepSeek API 키 형식 검증 완료")
                asyncio.create_task(validate_api_key_connection_async())
        else:
            print("[WARNING] LLM_API_KEY가 설정되지 않았습니다. 번역 기능이 작동하지 않을 수 있습니다.")
    except Exception as e:
        print(f"[WARNING] API 키 검증 중 오류 (서버는 계속 실행됩니다): {e}")
        import traceback
        traceback.print_exc()
    
    # 운영: Cloudflare Cron 사용 시 서버 내 스케줄러 비활성화 (중복 실행 방지)
    if os.getenv("DISABLE_IN_PROCESS_SCHEDULER", "").lower() in ("1", "true", "yes"):
        print("[OK] In-process scheduler disabled (Cloudflare Cron will trigger jobs)")
    else:
        start_scheduler()

    # 새 DB 연결 직후 스케줄러(15분) 전에 빈 DB 문제 방지: 시작 시 FMP 캘린더/뉴스 1회 비동기 수집
    print("[SYSTEM] Startup: Initial data fetch triggered")
    asyncio.create_task(startup_initial_data_fetch())

    yield
    shutdown_scheduler()


async def startup_initial_data_fetch():
    """서버 기동 직후 FMP 3종(캘린더·뉴스·지수) 1회 비동기 수집 — 스케줄러 대기 없이 빈 DB 채움."""
    try:
        await asyncio.sleep(1)  # DB/엔진 준비 대기
        from app.services.calendar_service import fetch_economic_calendar
        from app.services.news_service import fetch_and_process_news
        from app.services.fmp_service import fetch_fmp_indexes
        await fetch_economic_calendar()
        await fetch_and_process_news()
        await fetch_fmp_indexes()
        print("[SYSTEM] Startup: Initial data fetch completed (calendar, news, indexes)")
    except Exception as e:
        print(f"[SYSTEM] Startup: Initial data fetch error: {e}")
        import traceback
        traceback.print_exc()


async def validate_api_key_connection_async():
    """백그라운드에서 API 키 연결 검증"""
    try:
        from app.services.llm_api_validator import validate_api_key_connection
        if os.getenv("LLM_API_KEY", ""):
            await asyncio.sleep(2)
            is_valid, error_msg = await validate_api_key_connection()
            if is_valid:
                print("[OK] DeepSeek API 키 연결 검증 성공")
            else:
                print(f"[ERROR] DeepSeek API 키 연결 검증 실패: {error_msg}")
    except Exception as e:
        print(f"[WARNING] API 키 연결 검증 중 오류: {e}")

app = FastAPI(
    title="Futures Terminal API",
    description="Futures Trading Terminal Backend API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS / WebSocket Origin: api.signalchart.kr 백엔드에 접속하는 프론트 도메인 허용 (403 방지)
_allowed_origins_env = (os.getenv("ALLOWED_ORIGINS") or os.getenv("CORS_ORIGINS") or "").strip()
if _allowed_origins_env:
    _origins = [s.strip() for s in _allowed_origins_env.split(",") if s.strip()]
else:
    _origins = [
        "http://localhost:3001", "http://localhost:3002", "http://127.0.0.1:3001", "http://127.0.0.1:3002",
        "https://signalchart.kr", "https://www.signalchart.kr",
    ]
# 운영에서 추가 도메인만 넣을 때도 signalchart 도메인은 유지되도록 병합
_extra = ["https://signalchart.kr", "https://www.signalchart.kr"]
for o in _extra:
    if o not in _origins:
        _origins.append(o)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # 4xx 상세 메시지는 서버 로그에만 기록
    print(f"[ERROR] HTTPException status={exc.status_code} detail={exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": "요청을 처리할 수 없습니다."},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # 상세 에러는 서버 로그에만 기록, 클라이언트에는 노출하지 않음
    print(f"[ERROR] Global Exception: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"message": "오류가 발생했습니다."},
    )

# 라우터 등록
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(pro.router, prefix="/api/pro", tags=["pro"])
app.include_router(support.router, prefix="/api/support", tags=["support"])
app.include_router(indicators.router, prefix="/api/indicators", tags=["indicators"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(indexes.router, prefix="/api/indexes", tags=["indexes"])
app.include_router(custom_events.router, prefix="/api", tags=["custom-events"])
app.include_router(ai.router, prefix="/api", tags=["ai"])
app.include_router(cron.router, prefix="/api")
app.include_router(websocket_router, prefix="/ws", tags=["websocket"])

@app.get("/")
async def root():
    return {"message": "Futures Terminal API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
