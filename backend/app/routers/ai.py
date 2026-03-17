from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Literal, Optional

from app.auth import get_current_active_user
from app.database import get_db
from app.models import User
from app.services.ai_chat_service import get_briefing_context
from app.services.llm_provider import briefing_analyst_reply


router = APIRouter()


class AskAIRequest(BaseModel):
    command: Literal["briefing", "news", "ask"] = "ask"
    symbol: Optional[str] = None
    message: str


class AskAIResponse(BaseModel):
    answer: str


@router.post("/ai/ask", response_model=AskAIResponse)
async def ask_ai(
    body: AskAIRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """
    개인 AI 비서(프라이빗) 응답용 엔드포인트.
    - DB에 메시지를 저장하지 않고
    - 웹소켓 브로드캐스트도 하지 않음
    """
    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Empty message")

    symbol = (body.symbol or "").strip() or "NQ1!"

    context = get_briefing_context(db, symbol)
    # FMP 에이전트: Quote, 해당 종목 뉴스, Key Metrics 주입 (데이터 기반 브리핑)
    try:
        from app.services.fmp_service import (
            get_fmp_quote_for_briefing,
            get_fmp_stock_news_for_briefing,
            get_fmp_key_metrics_for_briefing,
        )
        context["fmp_quote_text"] = await get_fmp_quote_for_briefing(symbol)
        context["fmp_news_text"] = await get_fmp_stock_news_for_briefing(symbol, limit=10)
        context["fmp_key_metrics_text"] = await get_fmp_key_metrics_for_briefing(symbol)
    except Exception:
        context.setdefault("fmp_quote_text", "")
        context.setdefault("fmp_news_text", "")
        context.setdefault("fmp_key_metrics_text", "")
    # FMP 데이터 한국어 번역
    try:
        from app.services.llm_provider import translate_fmp_blob_to_korean
        for key in ("fmp_quote_text", "fmp_news_text", "fmp_key_metrics_text"):
            if context.get(key):
                context[key] = await translate_fmp_blob_to_korean(context[key])
    except Exception:
        pass
    # 이벤트/최신 뉴스 질문이면 웹 검색 병행
    try:
        from app.services.web_search_service import get_web_search_for_briefing
        context["web_search_text"] = await get_web_search_for_briefing(msg, symbol)
    except Exception:
        context.setdefault("web_search_text", "")

    # 커맨드별로 LLM에 주는 user_message를 살짝 조정
    if body.command == "briefing":
        user_message = f"[프라이빗 브리핑 요청] {msg}"
    elif body.command == "news":
        user_message = f"[프라이빗 뉴스 요약 요청] {msg}"
    else:
        user_message = f"[프라이빗 질문] {msg}"

    answer = await briefing_analyst_reply(symbol=symbol, user_message=user_message, context=context)
    return AskAIResponse(answer=answer)

