"""
경제 지표 및 실적 API 엔드포인트
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import EconomicIndicator, Earnings
from app.schemas import IndicatorResponse, EarningsResponse
from typing import List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/indicators", response_model=List[IndicatorResponse])
async def get_indicators(
    country: str = "US",
    category: str = None,
    released_only: bool = False,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """경제 지표 조회 (미국·중국: country=US 또는 CN 또는 US,CN)"""
    countries = [c.strip().upper() for c in country.split(",") if c.strip()]
    if not countries:
        countries = ["US"]
    if len(countries) == 1:
        query = db.query(EconomicIndicator).filter(EconomicIndicator.country == countries[0])
    else:
        query = db.query(EconomicIndicator).filter(EconomicIndicator.country.in_(countries))

    total_before_filter = query.count()
    if category:
        query = query.filter(EconomicIndicator.category == category)
    after_category = query.count()
    if released_only:
        query = query.filter(EconomicIndicator.is_released == True)
    after_released = query.count()

    indicators = query.order_by(
        EconomicIndicator.release_date.desc()
    ).limit(limit).all()
    api_count = len(indicators)
    logger.info(
        "[INDICATORS API] country=%s released_only=%s limit=%s | "
        "db_total=%s after_category=%s after_released_filter=%s => api_recent_results_count=%s",
        country, released_only, limit, total_before_filter, after_category, after_released, api_count
    )
    if indicators and api_count <= 2:
        for ind in indicators[:2]:
            logger.info("[INDICATORS API] sample: id=%s name=%s release_date=%s is_released=%s",
                        ind.id, ind.name, ind.release_date, ind.is_released)

    return [IndicatorResponse.model_validate(ind) for ind in indicators]


@router.get("/earnings", response_model=List[EarningsResponse])
async def get_earnings(
    symbol: str = None,
    limit: int = 20,
    date: str = None,  # "today" = KST 오늘 날짜만 (오늘의 실적)
    db: Session = Depends(get_db)
):
    """기업 실적 조회. date=today 시 KST 오늘 실적만 반환 (인베스팅 08:00 갱신 데이터)."""
    from datetime import timezone
    
    query = db.query(Earnings)
    
    if symbol:
        query = query.filter(Earnings.symbol == symbol)
    
    if date == "today":
        kst = timezone(timedelta(hours=9))
        today_start = datetime.now(kst).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        today_start_utc = today_start.astimezone(timezone.utc)
        today_end_utc = today_end.astimezone(timezone.utc)
        query = query.filter(
            Earnings.earnings_date >= today_start_utc,
            Earnings.earnings_date < today_end_utc,
        )
    else:
        future_date = datetime.utcnow() + timedelta(days=30)
        query = query.filter(Earnings.earnings_date <= future_date)
    
    earnings = query.order_by(
        Earnings.earnings_date.asc()
    ).limit(limit).all()
    
    return [EarningsResponse.model_validate(earn) for earn in earnings]
