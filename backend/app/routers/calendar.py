"""
경제 캘린더 API 엔드포인트
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import EconomicCalendar, CustomEvent
from app.schemas import CalendarResponse, MergedEventResponse
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/news-summary", response_model=List[CalendarResponse])
async def get_news_summary(db: Session = Depends(get_db)):
    """뉴스정리 전용: DB에 저장된 뉴스만 조회 (저수지 패턴 — 외부 API 직접 호출 없음)."""
    from app.models import News
    import re as re_mod

    start_date = datetime.utcnow() - timedelta(days=2)
    end_date = datetime.utcnow() + timedelta(days=7)
    aljazeera_news = db.query(News).filter(
        News.source == "Al Jazeera",
        News.created_at >= start_date,
        News.created_at <= end_date
    ).order_by(News.created_at.desc()).limit(10).all()
    # DB에 없으면 빈 목록 반환 (FMP 수집은 스케줄러/startup에서만 수행)
    if not aljazeera_news:
        aljazeera_news = db.query(News).filter(
            News.created_at >= start_date,
            News.created_at <= end_date
        ).order_by(News.created_at.desc()).limit(5).all()

    result = []
    for news in aljazeera_news[:5]:
        result.append(CalendarResponse(
            id=news.id + 1000000,
            event_name=news.original_title,
            ko_event_name=news.ko_title or news.original_title,
            country="Global",
            category="news",
            importance=news.importance or "normal",
            scheduled_time=news.created_at,
            actual_value="NEWS",
            forecast_value=None,
            previous_value=None,
            source=news.source,
            is_released=True,
            link=news.original_link,
            created_at=news.created_at,
            updated_at=news.created_at
        ))

    def _norm(s: str) -> str:
        if not s:
            return ""
        s = re_mod.sub(r"[,،]+", " ", s.strip().lower())
        s = re_mod.sub(r"\s*의\s*", " ", s)
        s = "".join(c for c in s if c.isalnum() or c.isspace())
        return re_mod.sub(r"\s+", " ", s).strip()[:50]

    seen = set()
    deduped = []
    for item in result:
        key = f"{(item.scheduled_time.strftime('%Y-%m-%d') if item.scheduled_time else '')}|{_norm(item.ko_event_name or item.event_name or '')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:5]


@router.get("/", response_model=List[CalendarResponse])
async def get_calendar(
    country: str = "US",
    days_ahead: int = 7,
    importance: str = None,  # low, medium, high, critical
    db: Session = Depends(get_db)
):
    """뉴스정리 패널: country=Global 이면 Al Jazeera 뉴스만 (https://www.aljazeera.com/news/). 그 외는 경제 캘린더."""
    from app.models import News
    import re as re_mod

    # 뉴스정리: Al Jazeera 헤드라인 5개만 (연준 파월 등 경제 일정 제외)
    if country == "Global":
        start_date = datetime.utcnow() - timedelta(days=2)
        end_date = datetime.utcnow() + timedelta(days=days_ahead)
        aljazeera_news = db.query(News).filter(
            News.source == "Al Jazeera",
            News.created_at >= start_date,
            News.created_at <= end_date
        ).order_by(News.created_at.desc()).limit(5).all()
        if not aljazeera_news:
            aljazeera_news = db.query(News).filter(
                News.created_at >= start_date,
                News.created_at <= end_date
            ).order_by(News.created_at.desc()).limit(5).all()
        result = []
        for news in aljazeera_news:
            result.append(CalendarResponse(
                id=news.id + 1000000,
                event_name=news.original_title,
                ko_event_name=news.ko_title or news.original_title,
                country="Global",
                category="news",
                importance=news.importance or "normal",
                scheduled_time=news.created_at,
                actual_value="NEWS",
                forecast_value=None,
                previous_value=None,
                source=news.source,
                is_released=True,
                link=news.original_link,
                created_at=news.created_at,
                updated_at=news.created_at
            ))
        # 중복 제거
        def _norm(s: str) -> str:
            if not s: return ""
            s = re_mod.sub(r"[,،]+", " ", s.strip().lower())
            s = re_mod.sub(r"\s*의\s*", " ", s)
            s = "".join(c for c in s if c.isalnum() or c.isspace())
            return re_mod.sub(r"\s+", " ", s).strip()[:50]
        seen = set()
        deduped = []
        for item in result:
            key = f"{(item.scheduled_time.strftime('%Y-%m-%d') if item.scheduled_time else '')}|{_norm(item.ko_event_name or item.event_name or '')}"
            if key in seen: continue
            seen.add(key)
            deduped.append(item)
        return deduped

    # 경제 캘린더 (country != Global) — timezone-aware UTC로 비교
    cal_start = datetime.now(timezone.utc)
    cal_end = cal_start + timedelta(days=days_ahead)
    query = db.query(EconomicCalendar).filter(
        EconomicCalendar.scheduled_time >= cal_start,
        EconomicCalendar.scheduled_time <= cal_end
    ).filter(EconomicCalendar.country == country)
    if importance:
        query = query.filter(EconomicCalendar.importance == importance)
    existing_events = query.order_by(
        EconomicCalendar.scheduled_time.asc(),
        EconomicCalendar.importance.desc()
    ).all()
    logger.info("[CALENDAR API get_calendar] country=%s days_ahead=%s cal_start=%s api_response_count=%s",
                country, days_ahead, cal_start.isoformat(), len(existing_events))
    return [CalendarResponse.model_validate(event) for event in existing_events]


def _kst_today_utc_range():
    """KST 기준 오늘 00:00 ~ 내일 00:00 을 UTC로 반환."""
    kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst)
    today_start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end_kst = today_start_kst + timedelta(days=1)
    return today_start_kst.astimezone(timezone.utc), today_end_kst.astimezone(timezone.utc)


def _kst_week_end_utc():
    """KST 기준 이번 주 일요일 23:59:59.999 를 UTC로 반환 (오늘 포함 ~ 일요일 끝)."""
    kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst)
    today_start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    # Python weekday: Mon=0 ... Sun=6. 일요일까지 며칠 남았는지
    days_until_sunday = (6 - now_kst.weekday()) % 7
    sunday_end_kst = today_start_kst + timedelta(days=days_until_sunday, hours=23, minutes=59, seconds=59)
    return sunday_end_kst.astimezone(timezone.utc)


@router.get("/today-events", response_model=List[CalendarResponse])
async def get_today_events(
    country: str = "US",
    importance: str = None,
    db: Session = Depends(get_db),
):
    """KST 기준 오늘 00:00~24:00 구간의 이벤트 (예정 이벤트 fallback용). timezone-aware."""
    today_start_utc, today_end_utc = _kst_today_utc_range()
    query = db.query(EconomicCalendar).filter(
        EconomicCalendar.scheduled_time >= today_start_utc,
        EconomicCalendar.scheduled_time < today_end_utc,
        EconomicCalendar.country == country,
    )
    if importance and (str(importance).strip()):
        lev = (importance or "").lower().strip()
        if lev == "low":
            query = query.filter(EconomicCalendar.importance.in_(["low", "medium", "high", "critical"]))
        elif lev == "medium":
            query = query.filter(EconomicCalendar.importance.in_(["medium", "high", "critical"]))
        else:
            query = query.filter(EconomicCalendar.importance.in_(["high", "critical"]))
    events = query.order_by(EconomicCalendar.scheduled_time.asc()).all()
    logger.info("[CALENDAR API today-events] country=%s today_start_utc=%s api_count=%s",
                country, today_start_utc.isoformat(), len(events))
    return [CalendarResponse.model_validate(e) for e in events]


@router.get("/upcoming", response_model=List[CalendarResponse])
async def get_upcoming_events(
    hours_ahead: int = 24,
    importance: str = "high",  # 최소 중요도 (low/medium/high). critical은 항상 포함.
    db: Session = Depends(get_db)
):
    """다가오는 중요 이벤트 조회 (향후 N시간). timezone-aware UTC 사용."""
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(hours=hours_ahead)

    # 디버그: DB 단계별 카운트
    total_table = db.query(EconomicCalendar).count()
    total_in_range = db.query(EconomicCalendar).filter(
        EconomicCalendar.scheduled_time >= start_date,
        EconomicCalendar.scheduled_time <= end_date,
    ).count()
    after_importance = db.query(EconomicCalendar).filter(
        EconomicCalendar.scheduled_time >= start_date,
        EconomicCalendar.scheduled_time <= end_date,
        EconomicCalendar.importance.in_(_importance_set(importance)),
    ).count()
    events = db.query(EconomicCalendar).filter(
        EconomicCalendar.scheduled_time >= start_date,
        EconomicCalendar.scheduled_time <= end_date,
        EconomicCalendar.importance.in_(_importance_set(importance)),
        EconomicCalendar.is_released == False
    ).order_by(
        EconomicCalendar.scheduled_time.asc()
    ).all()
    api_count = len(events)
    logger.info(
        "[CALENDAR API upcoming] hours_ahead=%s importance=%s start_date=%s | "
        "db_total=%s db_in_range=%s after_importance=%s after_is_released=False => api_upcoming_events_count=%s",
        hours_ahead, importance, start_date.isoformat(), total_table, total_in_range, after_importance, api_count
    )
    if events and api_count <= 2:
        for e in events[:2]:
            logger.info("[CALENDAR API upcoming] sample: id=%s scheduled_time=%s is_released=%s country=%s",
                        e.id, e.scheduled_time, e.is_released, e.country)
    
    return [CalendarResponse.model_validate(event) for event in events]


def _importance_set(min_level: str) -> List[str]:
    s = (min_level or "low").lower().strip()
    if s == "low":
        return ["low", "medium", "high", "critical"]
    if s == "medium":
        return ["medium", "high", "critical"]
    return ["high", "critical"]


@router.get("/board", response_model=List[MergedEventResponse])
async def get_calendar_board(
    symbol: Optional[str] = None,
    hours_ahead: int = 168,
    importance: str = "low",
    range_filter: Optional[str] = None,  # "today" = KST 오늘만, "week" = 오늘 ~ 이번 주 일요일
    db: Session = Depends(get_db),
):
    """
    지표/일정 통합 보드: economic + custom 이벤트를 시간순 리스트로 반환.
    range_filter=today: KST 오늘 00:00~24:00만. range_filter=week: 오늘 ~ 이번 주 일요일 23:59.
    """
    today_start_utc, today_end_utc = _kst_today_utc_range()
    week_end_utc = _kst_week_end_utc()

    if (range_filter or "").strip().lower() == "today":
        # 오늘 일정: KST 오늘 해당만
        economic_events = (
            db.query(EconomicCalendar)
            .filter(
                EconomicCalendar.scheduled_time >= today_start_utc,
                EconomicCalendar.scheduled_time < today_end_utc,
            )
            .order_by(EconomicCalendar.scheduled_time.asc())
            .all()
        )
        custom_events = (
            db.query(CustomEvent)
            .filter(
                CustomEvent.is_active == True,
                CustomEvent.event_date >= today_start_utc,
                CustomEvent.event_date < today_end_utc,
            )
            .order_by(CustomEvent.event_date.asc())
            .all()
        )
    elif (range_filter or "").strip().lower() == "week":
        # 이번 주 일정: 오늘 ~ 이번 주 일요일 23:59
        economic_events = (
            db.query(EconomicCalendar)
            .filter(
                EconomicCalendar.scheduled_time >= today_start_utc,
                EconomicCalendar.scheduled_time <= week_end_utc,
            )
            .order_by(EconomicCalendar.scheduled_time.asc())
            .all()
        )
        custom_events = (
            db.query(CustomEvent)
            .filter(
                CustomEvent.is_active == True,
                CustomEvent.event_date >= today_start_utc,
                CustomEvent.event_date <= week_end_utc,
            )
            .order_by(CustomEvent.event_date.asc())
            .all()
        )
    else:
        # 기본: 최근 50건 (기존 동작)
        economic_events = (
            db.query(EconomicCalendar)
            .order_by(EconomicCalendar.scheduled_time.desc())
            .limit(50)
            .all()
        )
        custom_events = (
            db.query(CustomEvent)
            .order_by(CustomEvent.event_date.desc())
            .limit(50)
            .all()
        )

    merged: List[MergedEventResponse] = []
    for e in economic_events:
        st = e.scheduled_time
        scheduled_at = st.isoformat() if st else ""
        title = (e.ko_event_name or e.event_name or "").strip()
        merged.append(MergedEventResponse(
            id=f"economic-{e.id}",
            type="economic",
            scheduled_at=scheduled_at,
            title=title or e.event_name,
            description=None,
            country=e.country,
            importance=e.importance,
            actual_value=e.actual_value,
            forecast_value=e.forecast_value,
            previous_value=e.previous_value,
            source_url=e.link,
            target_symbol=None,
        ))
    for c in custom_events:
        ed = c.event_date
        scheduled_at = ed.isoformat() if ed else ""
        merged.append(MergedEventResponse(
            id=f"custom-{c.id}",
            type="custom",
            scheduled_at=scheduled_at,
            title=c.title or "",
            description=c.description,
            country=None,
            importance=c.importance,
            actual_value=None,
            forecast_value=None,
            previous_value=None,
            source_url=c.link,
            target_symbol=c.target_symbol,
        ))

    merged.sort(key=lambda x: x.scheduled_at)
    logger.info("[CALENDAR API board] symbol=%s range=%s merged_count=%s", symbol, range_filter, len(merged))
    return merged
