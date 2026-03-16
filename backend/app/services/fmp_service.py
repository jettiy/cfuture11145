"""
FMP (Financial Modeling Prep) API — 경제 캘린더 수집
엔드포인트: https://financialmodelingprep.com/api/v3/economic_calendar
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

FMP_API_KEY = os.getenv("FMP_API_KEY", "")
FMP_ECONOMIC_CALENDAR_URL = "https://financialmodelingprep.com/api/v3/economic_calendar"


def _parse_fmp_datetime(date_str: Optional[str], time_str: Optional[str]) -> Optional[datetime]:
    """FMP date/time을 UTC datetime으로 변환. date는 YYYY-MM-DD 또는 YYYY-MM-DD HH:MM:SS, time은 HH:MM:SS 또는 생략."""
    if not date_str or not str(date_str).strip():
        return None
    try:
        s = str(date_str).strip()
        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s[:19] if len(s) >= 19 else s[:10], fmt)
                break
            except ValueError:
                continue
        if not dt:
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        if time_str and str(time_str).strip() and (dt.hour == 0 and dt.minute == 0):
            t = str(time_str).strip()
            if ":" in t:
                parts = t.split(":")
                hour = int(parts[0]) if parts[0].isdigit() else 12
                minute = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                dt = dt.replace(hour=min(hour, 23), minute=min(minute, 59), second=0, microsecond=0)
        if dt.hour == 0 and dt.minute == 0:
            dt = dt.replace(hour=12, minute=0, second=0, microsecond=0)
        return dt.replace(tzinfo=timezone.utc)
    except Exception as e:
        logger.warning("[FMP] parse datetime failed date=%s time=%s: %s", date_str, time_str, e)
        return None


def _normalize_fmp_event(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """FMP 경제 캘린더 항목을 EconomicCalendar 모델 포맷으로 정규화.
    FMP 필드: event(또는 name), date, time, country, impact, actual, estimate, previous 등.
    """
    try:
        event_name = (raw.get("event") or raw.get("name") or raw.get("title") or "").strip()
        if not event_name:
            return None
        date_str = raw.get("date")
        time_str = raw.get("time") or raw.get("releaseTime")
        scheduled = _parse_fmp_datetime(date_str, time_str)
        if not scheduled:
            return None
        country = (raw.get("country") or "US").strip() or "US"
        if country.upper() in ("USA", "UNITED STATES"):
            country = "US"
        actual = raw.get("actual")
        estimate = raw.get("estimate") or raw.get("forecast") or raw.get("forecastValue")
        previous = raw.get("previous") or raw.get("previousValue")
        actual_value = str(actual).strip() if actual is not None and str(actual).strip() else None
        forecast_value = str(estimate).strip() if estimate is not None and str(estimate).strip() else None
        previous_value = str(previous).strip() if previous is not None and str(previous).strip() else None
        importance = "medium"
        impact = raw.get("impact") or raw.get("importance")
        if impact is not None:
            if isinstance(impact, str):
                impact_lower = impact.lower()
                if impact_lower in ("high", "critical", "high impact"):
                    importance = "high"
                elif impact_lower in ("medium", "medium impact"):
                    importance = "medium"
                elif impact_lower in ("low", "low impact"):
                    importance = "low"
            elif isinstance(impact, (int, float)) and impact >= 2:
                importance = "high"
        return {
            "event_name": event_name,
            "ko_event_name": None,
            "country": country,
            "category": raw.get("category") or "general",
            "importance": importance,
            "scheduled_time": scheduled,
            "actual_value": actual_value,
            "forecast_value": forecast_value,
            "previous_value": previous_value,
            "source": "FMP",
            "is_released": actual is not None,
            "link": raw.get("link") or raw.get("url"),
        }
    except Exception as e:
        logger.warning("[FMP] normalize event failed: %s", e)
        return None


async def get_economic_calendar(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    FMP 경제 캘린더 API 호출.
    https://financialmodelingprep.com/api/v3/economic_calendar?from=...&to=...&apikey=...
    반환: EconomicCalendar에 upsert 가능한 dict 리스트.
    """
    api_key = (os.getenv("FMP_API_KEY") or FMP_API_KEY or "").strip()
    if not api_key:
        logger.warning("[FMP] FMP_API_KEY not set, economic calendar skipped")
        print("[FMP] FMP_API_KEY not set, economic calendar skipped")
        return []
    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()
    if not from_date:
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    if not to_date:
        to_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    url = FMP_ECONOMIC_CALENDAR_URL
    params = {"from": from_date, "to": to_date, "apikey": api_key}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, params=params)
        if r.status_code != 200:
            logger.error("[FMP] economic calendar HTTP status=%s body=%s", r.status_code, (r.text or "")[:300])
            print(f"[FMP] economic calendar HTTP error: status={r.status_code}")
            return []
        data = r.json()
        raw_list = data if isinstance(data, list) else (data.get("economicCalendar") or data.get("data") or [])
        if not raw_list:
            print(f"[FMP] economic calendar empty: from={from_date} to={to_date}")
            return []
        normalized = []
        for item in raw_list:
            n = _normalize_fmp_event(item)
            if n:
                normalized.append(n)
        print(f"[FMP] Successfully fetched {len(normalized)} events")
        logger.info("[FMP] economic calendar from=%s to=%s raw=%s normalized=%s", from_date, to_date, len(raw_list), len(normalized))
        return normalized
    except httpx.RequestError as e:
        logger.exception("[FMP] economic calendar request error: %s", e)
        print(f"[FMP] economic calendar request error: {e}")
        return []
    except Exception as e:
        logger.exception("[FMP] economic calendar error: %s", e)
        print(f"[FMP] economic calendar error: {e}")
        return []
