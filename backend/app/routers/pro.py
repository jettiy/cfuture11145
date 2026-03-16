from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, SupportChat, UserRole
from app.schemas import ProUpgradeRequest
from app.auth import get_current_active_user
from app.services.google_sheets_service import sync_user_to_sheet

router = APIRouter()

@router.post("/request-upgrade")
async def request_pro_upgrade(
    request: ProUpgradeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """PRO 업그레이드 요청"""
    # 이미 PRO 이상이면 에러
    if current_user.role in [UserRole.PRO, UserRole.ADMIN]:
        raise HTTPException(status_code=400, detail="Already PRO or Admin")
    
    # 이미 진행 중인 요청이 있는지 체크 (pending 또는 in_progress)
    if current_user.pro_request_status in ["pending", "in_progress"]:
        raise HTTPException(status_code=400, detail="PRO upgrade request already pending")
    
    # 이미 진행 중인 상담 채팅이 있는지 확인
    existing_chat = db.query(SupportChat).filter(
        SupportChat.user_id == current_user.id,
        SupportChat.status.in_(["pending", "active"]),
        SupportChat.request_type == "pro_upgrade"
    ).first()
    if existing_chat:
        raise HTTPException(status_code=400, detail="이미 진행 중인 PRO 업그레이드 상담이 있습니다.")
    
    # 이메일/전화번호 중복 체크 (다른 사용자가 사용 중인지)
    if request.email:
        existing_email = db.query(User).filter(
            User.email == request.email,
            User.id != current_user.id
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    if request.phone:
        existing_phone = db.query(User).filter(
            User.phone == request.phone,
            User.id != current_user.id
        ).first()
        if existing_phone:
            raise HTTPException(status_code=400, detail="Phone already registered")
    
    # 사용자 정보 업데이트
    current_user.name = request.name
    current_user.phone = request.phone
    current_user.email = request.email
    current_user.pro_request_status = "pending"
    
    # 상담 채팅 생성
    support_chat = SupportChat(
        user_id=current_user.id,
        status="pending",
        request_type="pro_upgrade"
    )
    db.add(support_chat)
    db.commit()
    db.refresh(support_chat)
    
    # 구글 시트 동기화 (신청 초기 데이터 전송)
    try:
        await sync_user_to_sheet(request.name, request.phone, request.email, "APPLICANT")
    except Exception as e:
        print(f"[PRO] Google sheets sync error: {e}")
    
    return {
        "message": "PRO upgrade request submitted",
        "chat_id": support_chat.id
    }


@router.get("/my-status")
async def get_my_pro_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """본인 PRO 신청 상태 조회"""
    # 진행 중인 상담 채팅 조회
    active_chat = db.query(SupportChat).filter(
        SupportChat.user_id == current_user.id,
        SupportChat.status.in_(["pending", "active"]),
        SupportChat.request_type == "pro_upgrade"
    ).first()
    
    return {
        "pro_request_status": current_user.pro_request_status,
        "role": current_user.role.value,
        "chat_id": active_chat.id if active_chat else None,
        "chat_status": active_chat.status if active_chat else None
    }
