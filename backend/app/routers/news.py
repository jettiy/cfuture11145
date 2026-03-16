from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import News
from app.schemas import NewsResponse
from app.services.news_interpretation_service import interpret_news
from typing import List
import time

router = APIRouter()
_NEWS_LIST_CACHE: dict = {}
_NEWS_CACHE_TTL_SEC = 20

@router.get("/", response_model=List[NewsResponse])
async def get_news(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    now = time.time()
    cache_key = ("list", limit)
    if cache_key in _NEWS_LIST_CACHE:
        cached_at, data = _NEWS_LIST_CACHE[cache_key]
        if now - cached_at < _NEWS_CACHE_TTL_SEC:
            return data
    news_list = db.query(News).order_by(
        News.created_at.desc()
    ).limit(limit).all()
    result = [NewsResponse.model_validate(n) for n in news_list]
    _NEWS_LIST_CACHE[cache_key] = (now, result)
    return result

@router.get("/breaking", response_model=List[NewsResponse])
async def get_breaking_news(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    news_list = db.query(News).filter(
        News.is_breaking == True
    ).order_by(News.created_at.desc()).limit(limit).all()
    return [NewsResponse.model_validate(n) for n in news_list]


@router.get("/{news_id}/interpret")
async def get_news_interpretation(news_id: int, db: Session = Depends(get_db)):
    """실시간 뉴스 해석: 해당 뉴스에 대해 해석 페르소나가 2~4문장으로 해석한 내용을 반환."""
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="News not found")
    title = news.ko_title or news.original_title or ""
    summary = news.ko_summary or news.original_summary
    if isinstance(summary, list):
        summary = "\n".join(str(s) for s in summary) if summary else None
    interpretation = await interpret_news(title, summary)
    if interpretation is None:
        raise HTTPException(status_code=503, detail="Interpretation temporarily unavailable")
    return {"news_id": news_id, "interpretation": interpretation}
