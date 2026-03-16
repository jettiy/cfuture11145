"""
Custom Events Router
관리자가 특별 이벤트를 등록/수정/삭제하는 API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.models import CustomEvent, User
from app.auth import get_current_user


router = APIRouter(prefix="/custom-events", tags=["custom-events"])


# Pydantic Models
class CustomEventCreate(BaseModel):
    title: str
    event_date: str  # ISO format
    description: Optional[str] = None
    target_symbol: Optional[str] = None
    importance: str = "high"
    link: Optional[str] = None


class CustomEventUpdate(BaseModel):
    title: Optional[str] = None
    event_date: Optional[str] = None
    description: Optional[str] = None
    target_symbol: Optional[str] = None
    importance: Optional[str] = None
    link: Optional[str] = None
    is_active: Optional[bool] = None


class CustomEventResponse(BaseModel):
    id: int
    title: str
    event_date: str
    description: Optional[str]
    target_symbol: Optional[str]
    importance: str
    link: Optional[str]
    is_active: bool
    created_by: Optional[int]
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """관리자 권한 확인"""
    if current_user.role.value != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )
    return current_user


def event_to_response(e: CustomEvent) -> CustomEventResponse:
    """CustomEvent 모델을 Response로 변환"""
    return CustomEventResponse(
        id=e.id,
        title=e.title,
        event_date=e.event_date.isoformat() if e.event_date else None,
        description=e.description,
        target_symbol=e.target_symbol,
        importance=e.importance,
        link=e.link,
        is_active=e.is_active,
        created_by=e.created_by,
        created_at=e.created_at.isoformat() if e.created_at else None,
        updated_at=e.updated_at.isoformat() if e.updated_at else None
    )


@router.get("", response_model=List[CustomEventResponse])
async def get_custom_events(
    symbol: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    커스텀 이벤트 목록 조회
    """
    try:
        query = db.query(CustomEvent)
        
        if active_only:
            query = query.filter(CustomEvent.is_active == True)
        
        if symbol:
            query = query.filter(
                or_(
                    CustomEvent.target_symbol == symbol,
                    CustomEvent.target_symbol == None
                )
            )
        
        events = query.order_by(CustomEvent.event_date.asc()).limit(limit).all()
        return [event_to_response(e) for e in events]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이벤트 조회 중 오류 발생: {str(e)}"
        )


@router.post("", response_model=CustomEventResponse)
async def create_custom_event(
    event_data: CustomEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    새 커스텀 이벤트 등록 (관리자 전용)
    """
    try:
        # 날짜 파싱
        try:
            event_date = datetime.fromisoformat(event_data.event_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="잘못된 날짜 형식입니다. ISO 형식을 사용하세요."
            )
        
        # 중요도 검증
        valid_importance = ["low", "medium", "high", "critical"]
        if event_data.importance not in valid_importance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"잘못된 중요도입니다. 가능한 값: {', '.join(valid_importance)}"
            )
        
        new_event = CustomEvent(
            title=event_data.title,
            event_date=event_date,
            description=event_data.description,
            target_symbol=event_data.target_symbol,
            importance=event_data.importance,
            link=event_data.link,
            is_active=True,
            created_by=current_user.id
        )
        
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        
        return event_to_response(new_event)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이벤트 등록 중 오류 발생: {str(e)}"
        )


@router.put("/{event_id}", response_model=CustomEventResponse)
async def update_custom_event(
    event_id: int,
    event_data: CustomEventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    커스텀 이벤트 수정 (관리자 전용)
    """
    try:
        event = db.query(CustomEvent).filter(CustomEvent.id == event_id).first()
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="이벤트를 찾을 수 없습니다."
            )
        
        # 업데이트할 필드 적용
        update_data = event_data.model_dump(exclude_unset=True)
        
        if "event_date" in update_data:
            try:
                update_data["event_date"] = datetime.fromisoformat(
                    update_data["event_date"].replace("Z", "+00:00")
                )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="잘못된 날짜 형식입니다."
                )
        
        if "importance" in update_data:
            valid_importance = ["low", "medium", "high", "critical"]
            if update_data["importance"] not in valid_importance:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="잘못된 중요도입니다."
                )
        
        for field, value in update_data.items():
            setattr(event, field, value)
        
        db.commit()
        db.refresh(event)
        
        return event_to_response(event)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이벤트 수정 중 오류 발생: {str(e)}"
        )


@router.delete("/{event_id}")
async def delete_custom_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    커스텀 이벤트 삭제 (관리자 전용)
    """
    try:
        event = db.query(CustomEvent).filter(CustomEvent.id == event_id).first()
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="이벤트를 찾을 수 없습니다."
            )
        
        db.delete(event)
        db.commit()
        
        return {"message": "이벤트가 삭제되었습니다.", "id": event_id}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이벤트 삭제 중 오류 발생: {str(e)}"
        )
