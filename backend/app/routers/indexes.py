"""
주요 지수 API — DB만 조회 (저수지 패턴). FMP 직접 호출 없음.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import IndexData
from app.schemas import IndexDataResponse

router = APIRouter()


@router.get("/", response_model=List[IndexDataResponse])
async def get_indexes(db: Session = Depends(get_db)):
    """DB에 저장된 주요 지수(나스닥, S&P500, 다우 등) 최신 스냅샷만 반환. 외부 API 호출 없음."""
    rows = db.query(IndexData).order_by(IndexData.updated_at.desc()).limit(20).all()
    return [IndexDataResponse.model_validate(r) for r in rows]
