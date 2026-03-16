"""
Cron 전용 라우터: Cloudflare Cron Worker가 단일로 호출합니다.
서버 내 APScheduler 대신 사용하여 다중 인스턴스 시 중복 실행을 방지합니다.
Authorization: Bearer <CRON_SECRET> 또는 X-Cron-Secret 헤더로 인증.
"""
import os
from fastapi import APIRouter, Header, HTTPException, Depends

router = APIRouter(prefix="/cron", tags=["cron"])

def verify_cron_secret(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None, alias="X-Cron-Secret"),
) -> None:
    """CRON_SECRET 환경 변수와 일치해야만 호출 허용."""
    secret = os.getenv("CRON_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="CRON_SECRET not configured")
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if not token:
        token = x_cron_secret
    if not token or token != secret:
        raise HTTPException(status_code=401, detail="Invalid cron secret")


@router.post("/news")
async def cron_fetch_news(_: None = Depends(verify_cron_secret)):
    """뉴스 수집 (봉 완성 주기: 1분 권장)."""
    from app.services.news_service import fetch_and_process_news
    await fetch_and_process_news()
    return {"ok": True, "job": "news"}


@router.post("/indicators")
async def cron_fetch_indicators(_: None = Depends(verify_cron_secret)):
    """경제 지표 업데이트 (5분 주기 권장)."""
    from app.services.indicators_service import fetch_economic_indicators
    await fetch_economic_indicators()
    return {"ok": True, "job": "indicators"}


@router.post("/earnings")
async def cron_fetch_earnings(_: None = Depends(verify_cron_secret)):
    """실적 데이터 업데이트 (5분 주기 권장)."""
    from app.services.indicators_service import fetch_earnings
    await fetch_earnings()
    return {"ok": True, "job": "earnings"}


@router.post("/calendar")
async def cron_fetch_calendar(_: None = Depends(verify_cron_secret)):
    """경제 캘린더 업데이트 (5분 주기 권장)."""
    from app.services.calendar_service import fetch_economic_calendar
    await fetch_economic_calendar()
    return {"ok": True, "job": "calendar"}


@router.post("/indexes")
async def cron_fetch_indexes(_: None = Depends(verify_cron_secret)):
    """주요 지수 수집 (FMP, 1분 주기 권장)."""
    from app.services.fmp_service import fetch_fmp_indexes
    await fetch_fmp_indexes()
    return {"ok": True, "job": "indexes"}


@router.post("/ai-chat")
async def cron_ai_chat(_: None = Depends(verify_cron_secret)):
    """(비활성화) AI 페르소나 채팅 제거됨."""
    return {"ok": True, "job": "ai-chat", "disabled": True}
