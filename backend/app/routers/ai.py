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

    # 컨텍스트는 기존 브리핑 컨텍스트 수집 로직을 재사용
    context = get_briefing_context(db, symbol)

    # 커맨드별로 LLM에 주는 user_message를 살짝 조정
    if body.command == "briefing":
        user_message = f"[프라이빗 브리핑 요청] {msg}"
    elif body.command == "news":
        user_message = f"[프라이빗 뉴스 요약 요청] {msg}"
    else:
        user_message = f"[프라이빗 질문] {msg}"

    answer = await briefing_analyst_reply(symbol=symbol, user_message=user_message, context=context)
    return AskAIResponse(answer=answer)

