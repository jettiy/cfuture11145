from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import UpdateNicknameRequest, UserResponse
from app.auth import get_current_active_user

router = APIRouter()

@router.put("/nickname", response_model=UserResponse)
async def update_nickname(
    request: UpdateNicknameRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # 중복 체크
    existing = db.query(User).filter(
        User.nickname == request.nickname,
        User.id != current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Nickname already taken")
    
    current_user.nickname = request.nickname
    db.commit()
    db.refresh(current_user)
    
    return UserResponse.model_validate(current_user)
