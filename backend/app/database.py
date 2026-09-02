from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from typing import Generator

try:
    from fastapi import Request
except ImportError:
    Request = None  # type: ignore

# DATABASE_URL 등은 환경 변수(Cloudflare Secrets 등)로만 주입. .env 직접 로드 금지.
# PostgreSQL이 없으면 SQLite 사용 (개발/테스트용)
# 환경변수에서 가져오되, PostgreSQL 연결이 실패하면 SQLite로 폴백
env_db_url = os.getenv("DATABASE_URL", "")

# SQLite를 기본값으로 사용 (DATABASE_URL 미설정 시). 설정 시 PostgreSQL 등 env_db_url 사용.
# PostgreSQL 사용 시 import/연결 실패하면 SQLite로 폴백 (로컬 최종 점검 등).
import pathlib as _pathlib
_db_dir = _pathlib.Path(__file__).parent.parent

def _sqlite_config():
    return f"sqlite:///{_db_dir / 'futures_terminal.db'}", {"check_same_thread": False, "timeout": 30}

if not env_db_url:
    DATABASE_URL, connect_args = _sqlite_config()
    print(f"Using SQLite database at: {_db_dir / 'futures_terminal.db'}")
else:
    DATABASE_URL = env_db_url
    connect_args = {}
    _use_pg = True
    try:
        _test_engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
        from sqlalchemy import text
        with _test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"[WARNING] DATABASE_URL 연결 실패, SQLite로 폴백: {e}")
        DATABASE_URL, connect_args = _sqlite_config()
        _use_pg = False
    if _use_pg:
        print("Using PostgreSQL database")

# 커넥션 풀: TimeoutError 방지를 위해 pool 확대, pool_pre_ping으로 stale 연결 방지
_engine_kw: dict = {"echo": False, "connect_args": connect_args}
if DATABASE_URL and "postgresql" in DATABASE_URL.lower():
    _engine_kw["pool_pre_ping"] = True
    _engine_kw["pool_size"] = 20
    _engine_kw["max_overflow"] = 10
    _engine_kw["pool_recycle"] = 300
engine = create_engine(DATABASE_URL, **_engine_kw)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# PostgreSQL 사용 시 RLS 세션 변수 설정용 (SQLite는 RLS 미지원)
IS_POSTGRESQL = "postgresql" in DATABASE_URL.lower() if DATABASE_URL else False


def get_db(request: Request = None) -> Generator:  # noqa: F811
    db = SessionLocal()
    try:
        if IS_POSTGRESQL and request is not None:
            _set_rls_context(db, request)
        yield db
    finally:
        db.close()


def _set_rls_context(db: Session, request: Request) -> None:
    """PostgreSQL RLS: 요청의 JWT에서 user_id, is_admin을 읽어 세션 변수로 설정."""
    try:
        auth = request.headers.get("Authorization") or request.headers.get("authorization")
        if not auth or not auth.startswith("Bearer "):
            return
        token = auth[7:]
        from jose import jwt as jose_jwt
        secret = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
        algo = os.getenv("JWT_ALGORITHM", "HS256")
        payload = jose_jwt.decode(token, secret, algorithms=[algo])
        username = payload.get("sub")
        if not username:
            return
        row = db.execute(text("SELECT id, role FROM users WHERE username = :u"), {"u": username}).fetchone()
        if not row:
            return
        user_id, role = row[0], (row[1] or "").strip()
        is_admin = str(role).upper() == "ADMIN"
        db.execute(text("SET LOCAL app.current_user_id = :id"), {"id": str(user_id)})
        db.execute(text("SET LOCAL app.is_admin = :v"), {"v": "true" if is_admin else "false"})
        # SET LOCAL은 트랜잭션 내에서만 유효하므로 commit 하지 않음
    except Exception:
        db.rollback()
        # RLS 미설정 시 해당 요청은 정책에 따라 행이 0건일 수 있음
