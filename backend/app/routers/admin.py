from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, update, delete
from app.database import get_db
from app.models import User, AdminLog, SupportChat, SupportMessage, Message, Signal
from app.auth import get_current_active_user, require_role
from typing import List
from app.models import UserRole
from app.schemas import UserListResponse, UpdateUserRoleRequest, SupportChatResponse, SupportMessageResponse, RespondToSupportRequest, AdminStatsResponse
from app.services.google_sheets_service import sync_user_to_sheet

router = APIRouter()

@router.get("/users", response_model=List[UserListResponse])
async def list_users(
    search: str = None,
    role: str = None,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    query = db.query(User)
    
    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%")) |
            (User.nickname.ilike(f"%{search}%"))
        )
    
    if role:
        try:
            # Enum 값이 대문자로 변경됨에 따라 입력값도 대문자로 변환
            query = query.filter(User.role == UserRole(role.upper()))
        except ValueError:
            pass
    
    result = []
    for u in query.all():
        try:
            result.append(UserListResponse.model_validate(u))
        except Exception as e:
            import traceback
            traceback.print_exc()
            continue
    return result

@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    total = db.query(User).count()
    member_count = db.query(User).filter(User.role == UserRole.MEMBER).count()
    pro_count = db.query(User).filter(User.role == UserRole.PRO).count()
    admin_count = db.query(User).filter(User.role == UserRole.ADMIN).count()
    pending = db.query(User).filter(User.pro_request_status == "pending").count()
    
    return {
        "total_users": total,
        "member_count": member_count,
        "pro_count": pro_count,
        "admin_count": admin_count,
        "pending_pro_requests": pending
    }

@router.delete("/users/{user_id}")
async def ban_user(
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """사용자 계정 삭제(밴). 본인은 삭제 불가."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="본인 계정은 삭제할 수 없습니다.")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    username = target.username
    try:
        # FK 정리: 메시지 user_id null, 시그널/상담/메시지 삭제 후 유저 삭제
        db.execute(update(Message).where(Message.user_id == user_id).values(user_id=None))
        db.execute(delete(Signal).where(Signal.user_id == user_id))
        for chat in db.query(SupportChat).filter(SupportChat.user_id == user_id).all():
            db.execute(delete(SupportMessage).where(SupportMessage.support_chat_id == chat.id))
        db.execute(delete(SupportChat).where(SupportChat.user_id == user_id))
        db.execute(delete(SupportMessage).where(SupportMessage.user_id == user_id))
        db.execute(update(AdminLog).where(AdminLog.target_user_id == user_id).values(target_user_id=None))
        db.execute(delete(AdminLog).where(AdminLog.admin_id == user_id))
        db.delete(target)
        db.commit()
        log = AdminLog(
            admin_id=current_user.id,
            action="user_ban",
            target_user_id=None,
            details=f"User {username} banned (deleted)"
        )
        db.add(log)
        db.commit()
        return {"message": "User banned successfully"}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ban failed: {str(e)}")

@router.put("/users/role", response_model=UserListResponse)
async def update_user_role(
    request: UpdateUserRoleRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(User.id == request.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_role = target_user.role.value
    target_user.role = request.role
    db.commit()
    
    # 로그 기록
    log = AdminLog(
        admin_id=current_user.id,
        action="role_change",
        target_user_id=target_user.id,
        details=f"Role changed from {old_role} to {request.role.value}"
    )
    db.add(log)
    db.commit()
    
    # 구글 시트 동기화 (PRO로 변경 시)
    if request.role == UserRole.PRO:
        await sync_user_to_sheet(target_user.name, target_user.phone, target_user.email, "PRO")
    
    return UserListResponse.model_validate(target_user)

@router.get("/support/inbox", response_model=List[SupportChatResponse])
async def get_support_inbox(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    chats = db.query(SupportChat).order_by(SupportChat.created_at.desc()).all()
    result = []
    for chat in chats:
        user = db.query(User).filter(User.id == chat.user_id).first()
        chat_data = SupportChatResponse.model_validate(chat)
        if user:
            chat_data.user_name = user.name
            chat_data.user_phone = user.phone
            chat_data.user_email = user.email
            chat_data.user_nickname = user.nickname
        result.append(chat_data)
    return result

@router.get("/support/chats/{chat_id}/messages", response_model=List[SupportMessageResponse])
async def get_support_messages(
    chat_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    messages = db.query(SupportMessage).filter(
        SupportMessage.support_chat_id == chat_id
    ).order_by(SupportMessage.created_at.asc()).all()
    return [SupportMessageResponse.model_validate(m) for m in messages]

@router.post("/support/chats/{chat_id}/respond")
async def respond_to_support(
    chat_id: int,
    request: RespondToSupportRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    chat = db.query(SupportChat).filter(SupportChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if not chat.admin_id:
        chat.admin_id = current_user.id
        chat.status = "active"
    
    message = SupportMessage(
        support_chat_id=chat_id,
        user_id=current_user.id,
        content=request.content,
        is_admin=True
    )
    db.add(message)
    db.commit()
    
    return {"message": "Response sent"}
