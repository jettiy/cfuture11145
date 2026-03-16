from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, SupportChat, SupportMessage
from app.schemas import SupportChatResponse, SupportMessageResponse, SendSupportMessageRequest
from app.auth import get_current_active_user
from typing import List

router = APIRouter()

@router.post("/create", response_model=SupportChatResponse)
async def create_support_chat(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """상담 채팅 생성"""
    # 이미 진행 중인 채팅이 있는지 확인
    existing_chat = db.query(SupportChat).filter(
        SupportChat.user_id == current_user.id,
        SupportChat.status.in_(["pending", "active"])
    ).first()
    
    if existing_chat:
        return SupportChatResponse.model_validate(existing_chat)
    
    # 새 채팅 생성
    chat = SupportChat(
        user_id=current_user.id,
        status="pending",
        request_type="general"
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    
    return SupportChatResponse.model_validate(chat)

@router.get("/my-chat", response_model=SupportChatResponse)
async def get_my_chat(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """내 상담 채팅 가져오기"""
    chat = db.query(SupportChat).filter(
        SupportChat.user_id == current_user.id
    ).order_by(SupportChat.created_at.desc()).first()
    
    if not chat:
        raise HTTPException(status_code=404, detail="No support chat found")
    
    return SupportChatResponse.model_validate(chat)

@router.get("/chats/{chat_id}/messages", response_model=List[SupportMessageResponse])
async def get_support_messages(
    chat_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """상담 메시지 가져오기"""
    chat = db.query(SupportChat).filter(SupportChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # 본인의 채팅인지 확인
    if chat.user_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    messages = db.query(SupportMessage).filter(
        SupportMessage.support_chat_id == chat_id
    ).order_by(SupportMessage.created_at.asc()).all()
    
    return [SupportMessageResponse.model_validate(m) for m in messages]

@router.post("/chats/{chat_id}/messages")
async def send_support_message(
    chat_id: int,
    request: SendSupportMessageRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """상담 메시지 전송"""
    chat = db.query(SupportChat).filter(SupportChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # 본인의 채팅인지 또는 관리자인지 확인
    if chat.user_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # 관리자가 첫 메시지를 보내면 채팅 활성화
    if current_user.role.value == "admin" and not chat.admin_id:
        chat.admin_id = current_user.id
        chat.status = "active"
    
    message = SupportMessage(
        support_chat_id=chat_id,
        user_id=current_user.id,
        content=request.content,
        is_admin=(current_user.role.value == "admin")
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    
    return SupportMessageResponse.model_validate(message)
