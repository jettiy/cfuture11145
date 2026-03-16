"""
경제 캘린더 데이터 수집 서비스 — 100% FMP API 단일 소스
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple

from app.database import SessionLocal
from app.models import EconomicCalendar
from app.services.llm_provider import translate_to_korean

logger = logging.getLogger(__name__)

# 발표 전후 이 시간(분) 안에 있는 일정만 10초 폴링 대상
INDICATOR_REALTIME_WINDOW_MINUTES = 5


def cleanup_old_calendar(db):
    """KST 기준 오늘·내일 데이터만 유지 (매일 갱신용)"""
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    two_days_later = today_start + timedelta(days=2)
    today_start_utc = today_start.astimezone(timezone.utc)
    two_days_later_utc = two_days_later.astimezone(timezone.utc)
    deleted = db.query(EconomicCalendar).filter(
        (EconomicCalendar.scheduled_time < today_start_utc) |
        (EconomicCalendar.scheduled_time >= two_days_later_utc)
    ).delete()
    db.commit()
    print(f"[CALENDAR] Cleaned up {deleted} old records (keeping today & tomorrow KST)")


def has_events_in_realtime_window(db) -> bool:
    """DB에 scheduled_time이 현재 시각 전후 5분 안에 있는 이벤트가 하나라도 있으면 True."""
    now_utc = datetime.now(timezone.utc)
    window = timedelta(minutes=INDICATOR_REALTIME_WINDOW_MINUTES)
    start = now_utc - window
    end = now_utc + window
    return db.query(EconomicCalendar).filter(
        EconomicCalendar.scheduled_time >= start,
        EconomicCalendar.scheduled_time <= end,
    ).limit(1).first() is not None


async def fetch_economic_calendar() -> Tuple[int, List[Dict[str, Any]]]:
    """
    경제 캘린더 수집: FMP API만 사용 (US 이벤트만).
    반환: (upserted_count, updated_actual_events).
    updated_actual_events: actual_value가 이번 호출로 갱신된 이벤트 목록 (웹소켓 알림용).
    """
    db = SessionLocal()
    updated_actual_events: List[Dict[str, Any]] = []
    try:
        cleanup_old_calendar(db)
        from app.services.fmp_service import get_economic_calendar as fetch_fmp_calendar
        now_utc = datetime.now(timezone.utc)
        today = now_utc.date()
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
        logger.info("[CALENDAR] FMP from=%s to=%s", from_date, to_date)
        print(f"[CALENDAR] FMP from={from_date} to={to_date}")
        items = await fetch_fmp_calendar(from_date=from_date, to_date=to_date)
        if not items:
            logger.info("[CALENDAR] FMP returned no events; check [FMP] logs above")
            return 0, updated_actual_events
        upserted = 0
        for it in items:
            try:
                dt = it.get("scheduled_time")
                if isinstance(dt, datetime) and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if not dt:
                    continue
                event_name = (it.get("event_name") or "").strip()
                if not event_name:
                    continue
                country = (it.get("country") or "US").strip() or "US"
                importance = (it.get("importance") or "medium").strip() or "medium"
                actual_value = it.get("actual_value")
                forecast_value = it.get("forecast_value")
                previous_value = it.get("previous_value")
                is_released = bool(it.get("is_released"))
                existing = db.query(EconomicCalendar).filter(
                    EconomicCalendar.event_name == event_name,
                    EconomicCalendar.scheduled_time == dt,
                    EconomicCalendar.country == country,
                ).first()
                if existing:
                    old_actual = existing.actual_value
                    existing.actual_value = actual_value
                    existing.forecast_value = forecast_value
                    existing.previous_value = previous_value
                    existing.is_released = is_released
                    existing.importance = importance
                    existing.source = "FMP"
                    existing.updated_at = datetime.now(timezone.utc)
                    # actual이 새로 들어왔거나 바뀐 경우만 알림용 목록에 추가
                    if actual_value is not None and str(actual_value).strip() and old_actual != actual_value:
                        updated_actual_events.append({
                            "id": existing.id,
                            "event_name": event_name,
                            "ko_event_name": existing.ko_event_name,
                            "scheduled_at": dt.isoformat(),
                            "actual_value": actual_value,
                            "forecast_value": forecast_value,
                            "previous_value": previous_value,
                            "is_released": is_released,
                        })
                else:
                    ko_name = None
                    try:
                        ko_name = await translate_to_korean(event_name, "경제 이벤트")
                    except Exception:
                        pass
                    cal = EconomicCalendar(
                        event_name=event_name,
                        ko_event_name=ko_name or event_name,
                        country=country,
                        category=it.get("category") or "general",
                        importance=importance,
                        scheduled_time=dt,
                        actual_value=actual_value,
                        forecast_value=forecast_value,
                        previous_value=previous_value,
                        is_released=is_released,
                        link=it.get("link"),
                        source="FMP",
                    )
                    db.add(cal)
                upserted += 1
            except Exception as ex:
                logger.warning("[CALENDAR] FMP item upsert failed: %s", ex)
                print(f"[CALENDAR] FMP item upsert failed: {ex}")
                continue
        db.commit()
        logger.info("[CALENDAR] FMP upserted=%s, updated_actuals=%s", upserted, len(updated_actual_events))
        print(f"[CALENDAR] FMP upserted={upserted}, updated_actuals={len(updated_actual_events)}")
        total_in_db = db.query(EconomicCalendar).count()
        print(f"[DEBUG-2] 현재 DB에 저장된 총 지표 개수: {total_in_db}")
        return upserted, updated_actual_events
    except Exception as e:
        logger.exception("[CALENDAR] FMP error: %s", e)
        print(f"[CALENDAR] FMP error: {e}")
        db.rollback()
        return 0, []
    finally:
        db.close()
