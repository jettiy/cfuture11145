from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.models import User, UserRole
from app.schemas import SignupRequest, TokenResponse, UserResponse
from app.auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_active_user, ACCESS_TOKEN_EXPIRE_HOURS
)

router = APIRouter()

@router.get("/check-email/{email}")
async def check_email(email: str, db: Session = Depends(get_db)):
    """이메일 중복 체크"""
    exists = db.query(User).filter(User.email == email).first() is not None
    return {"available": not exists, "message": "Email already registered" if exists else "Email available"}

@router.get("/check-phone/{phone}")
async def check_phone(phone: str, db: Session = Depends(get_db)):
    """전화번호 중복 체크"""
    exists = db.query(User).filter(User.phone == phone).first() is not None
    return {"available": not exists, "message": "Phone already registered" if exists else "Phone available"}

@router.get("/check-username/{username}")
async def check_username(username: str, db: Session = Depends(get_db)):
    """아이디(사용자명) 중복 체크 - DB에 없으면 사용 가능(available: true). 오류 시에도 200 반환해 프론트 오류 방지."""
    try:
        exists = db.query(User).filter(User.username == username).first() is not None
        return {
            "available": not exists,
            "message": "Username already taken" if exists else "Username available"
        }
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"Error in check_username: {error_msg}")
        traceback.print_exc()
        # 모든 예외에서 500 대신 200 + available: true 반환. 실제 중복은 signup 단계에서 걸러짐.
        return {
            "available": True,
            "message": "Username check skipped (temporary error). You can try signing up."
        }

@router.post("/signup", response_model=TokenResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    try:
        # 중복 체크
        if db.query(User).filter(User.username == request.username).first():
            raise HTTPException(status_code=400, detail="Username already taken")
        if db.query(User).filter(User.nickname == request.nickname).first():
            raise HTTPException(status_code=400, detail="Nickname already taken")
        
        # 사용자 생성 (이름/연락처/이메일은 PRO 요청 시 입력)
        user = User(
            username=request.username,
            password_hash=get_password_hash(request.password),
            nickname=request.nickname,
            role=UserRole.MEMBER,
            pro_request_status="none"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # 토큰 생성
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        )
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user)
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"Signup error: {error_msg}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Signup failed: {error_msg}"
        )

@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    try:
        user = db.query(User).filter(User.username == form_data.username).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not verify_password(form_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        )
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse.model_validate(user)
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Login error: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return UserResponse.model_validate(current_user)
