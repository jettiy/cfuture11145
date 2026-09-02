from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Channel, Message, User, UserRole
from app.schemas import MessageResponse, SendMessageRequest, ChannelResponse
from app.auth import get_current_active_user
from typing import List

def _is_image_content(content: str) -> bool:
    if not content or len(content) < 50:
        return False
    c = content.strip()
    return c.startswith("data:image") or c.startswith("[IMAGE]:")

router = APIRouter()

@router.get("/channels", response_model=List[ChannelResponse])
async def get_channels(db: Session = Depends(get_db)):
    return [ChannelResponse.model_validate(c) for c in db.query(Channel).all()]

@router.get("/channels/{channel_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    channel_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    messages = db.query(Message).filter(
        Message.channel_id == channel_id
    ).order_by(Message.created_at.desc()).limit(limit).all()
    
    result = []
    for msg in reversed(messages):
        user = db.query(User).filter(User.id == msg.user_id).first() if msg.user_id else None
        result.append(MessageResponse(
            id=msg.id,
            channel_id=msg.channel_id,
            user_id=msg.user_id,
            username=user.username if user else None,
            nickname=user.nickname if user else None,
            content=msg.content,
            is_bot=msg.is_bot,
            user_role=user.role if user else None,
            created_at=msg.created_at
        ))
    
    return result

@router.post("/messages", response_model=MessageResponse)
async def send_message(
    request: SendMessageRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    channel = db.query(Channel).filter(Channel.id == request.channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # 이미지 업로드: Pro/Admin만 허용
    if _is_image_content(request.content):
        if current_user.role not in (UserRole.PRO, UserRole.ADMIN):
            raise HTTPException(status_code=403, detail="이미지 업로드는 PRO 또는 관리자만 가능합니다.")

    message = Message(
        channel_id=request.channel_id,
        user_id=current_user.id,
        content=request.content.strip(),
        is_bot=False
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    
    return MessageResponse(
        id=message.id,
        channel_id=message.channel_id,
        user_id=message.user_id,
        username=current_user.username,
        nickname=current_user.nickname,
        content=message.content,
        is_bot=message.is_bot,
        user_role=current_user.role,
        created_at=message.created_at
    )
