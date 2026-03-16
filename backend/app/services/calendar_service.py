"""
경제 캘린더 데이터 수집 서비스
소스: https://kr.investing.com/economic-calendar (스크래핑) → 실패 시 FMP 경제 캘린더 API
"""
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import EconomicCalendar
from app.services.llm_provider import translate_to_korean

logger = logging.getLogger(__name__)


def _investing_calendar_urls_with_date() -> List[str]:
    """오늘 날짜(KST)를 명시한 URL 우선 (오늘 지표가 반드시 포함되도록)"""
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    today_str = now.strftime("%Y-%m-%d")
    date_param = f"?date={today_str}"
    return [
        f"https://kr.investing.com/economic-calendar/{date_param}",
        f"https://kr.investing.com/economic-calendar/?date={today_str}",
        "https://kr.investing.com/economic-calendar/",
        f"https://m.kr.investing.com/economic-calendar/{date_param}",
        "https://m.kr.investing.com/economic-calendar/",
    ]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "max-age=0",
}


def cleanup_old_calendar(db: Session):
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


def _parse_event_time(time_str: str, kst: timezone) -> Optional[datetime]:
    if not time_str or not time_str.strip():
        return None
    s = time_str.strip()[:19]
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            event_dt = datetime.strptime(s, fmt)
            return event_dt.replace(tzinfo=kst).astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _get_country_from_row(row) -> Optional[str]:
    ALLOWED = {"us", "cn", "usa", "kr", "jp", "eu", "gb", "de"}
    c = (row.get("data-country") or "").strip().lower()
    if c in ("us", "usa"):
        return "US"
    if c == "cn":
        return "CN"
    if c in ("kr", "korea"):
        return "KR"
    if c in ("jp", "japan"):
        return "JP"
    if c in ("eu", "euro"):
        return "EU"
    if c in ("gb", "uk"):
        return "GB"
    if c == "de":
        return "DE"
    flag_td = row.find("td", class_=re.compile(r"flag|country", re.I))
    if flag_td:
        span = flag_td.find("span", class_=re.compile(r"ceFlags|flag", re.I))
        if span and span.get("class"):
            for cl in span.get("class", []):
                if cl.lower() in ALLOWED:
                    if cl.lower() in ("us", "usa"):
                        return "US"
                    if cl.lower() == "cn":
                        return "CN"
                    if cl.lower() in ("kr", "korea"):
                        return "KR"
                    if cl.lower() in ("jp", "japan"):
                        return "JP"
                    return "US"  # 기본
    return None


def _importance_from_sentiment(row) -> str:
    """캘린더 행의 sentiment 아이콘 개수로 importance 반환 (low/medium/high/critical)"""
    sentiment_cell = row.find("td", class_="sentiment")
    if not sentiment_cell:
        return "medium"
    count = len(sentiment_cell.find_all("i", class_="grayFullBullishIcon"))
    if count >= 3:
        return "critical"
    if count == 2:
        return "high"
    if count == 1:
        return "medium"
    return "low"


async def _fetch_investing_calendar_rows() -> List:
    """kr.investing.com/economic-calendar 페이지에서 오늘 날짜 이벤트 행 목록 반환"""
    urls = _investing_calendar_urls_with_date()
    for url in urls:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                r = await client.get(url, headers={**HEADERS, "Accept-Encoding": "gzip, deflate"})
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                table = soup.find("table", id="economicCalendarData")
                if not table:
                    table = soup.find("table", class_=re.compile(r"economic|calendar", re.I))
                rows = []
                if table:
                    tbody = table.find("tbody")
                    if tbody:
                        rows = tbody.find_all("tr", class_="js-event-item")
                    if not rows:
                        rows = table.find_all("tr", class_="js-event-item")
                if not rows:
                    rows = soup.find_all("tr", class_="js-event-item")
                if not rows and table:
                    for tr in table.find_all("tr"):
                        if tr.get("data-event-datetime"):
                            rows.append(tr)
                if rows:
                    return rows
        except Exception as e:
            print(f"[CALENDAR] Fetch error {url}: {e}")
            continue
    return []


async def fetch_economic_calendar():
    """경제 캘린더 수집: https://kr.investing.com/economic-calendar (매일 기준 갱신)"""
    db = SessionLocal()
    kst = timezone(timedelta(hours=9))

    try:
        cleanup_old_calendar(db)
        rows = await _fetch_investing_calendar_rows()
        if not rows:
            print("[CALENDAR] No rows from Investing.com economic-calendar, using FMP economic calendar")
            try:
                from app.services.fmp_service import get_economic_calendar as fetch_fmp_calendar
                now_utc = datetime.now(timezone.utc)
                today = now_utc.date()
                from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
                to_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
                logger.info("[CALENDAR] FMP fallback from=%s to=%s", from_date, to_date)
                print(f"[CALENDAR] FMP fallback from={from_date} to={to_date}")
                items = await fetch_fmp_calendar(from_date=from_date, to_date=to_date)
                if not items:
                    logger.info("[CALENDAR] FMP fallback returned no events; check [FMP] logs above")
                    return
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
                            existing.actual_value = actual_value
                            existing.forecast_value = forecast_value
                            existing.previous_value = previous_value
                            existing.is_released = is_released
                            existing.importance = importance
                            existing.source = "FMP"
                            existing.updated_at = datetime.now(timezone.utc)
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
                logger.info("[CALENDAR] FMP upserted=%s", upserted)
                print(f"[CALENDAR] FMP upserted={upserted}")
                total_in_db = db.query(EconomicCalendar).count()
                print(f"[DEBUG-2] 현재 DB에 저장된 총 지표 개수: {total_in_db}")
            except Exception as e:
                logger.exception("[CALENDAR] FMP fallback error: %s", e)
                print(f"[CALENDAR] FMP fallback error: {e}")
            return

        print(f"[CALENDAR] Scraping kr.investing.com/economic-calendar ({len(rows)} rows)")
        updated = 0
        for row in rows:
            try:
                time_str = row.get("data-event-datetime", "")
                if not time_str:
                    continue
                event_dt = _parse_event_time(time_str, kst)
                if not event_dt:
                    continue

                event_cell = row.find("td", class_="event") or row.find("div", class_="event")
                if not event_cell:
                    continue
                event_name = event_cell.get_text(strip=True)
                if not event_name:
                    continue

                country = _get_country_from_row(row)
                if not country:
                    txt = (row.get_text() or "") + " " + (event_cell.get_text() or "")
                    txt_lower = txt.lower()
                    if "미국" in txt or "united states" in txt_lower or "fed " in txt_lower:
                        country = "US"
                    elif "중국" in txt or "china" in txt_lower or "pbc" in txt_lower:
                        country = "CN"
                    elif "한국" in txt or "korea" in txt_lower or "bok" in txt_lower:
                        country = "KR"
                    else:
                        country = "US"

                act_td = row.find("td", class_="act")
                fore_td = row.find("td", class_="fore")
                prev_td = row.find("td", class_="prev")
                actual_value = act_td.get_text(strip=True) if act_td else None
                forecast_value = fore_td.get_text(strip=True) if fore_td else None
                previous_value = prev_td.get_text(strip=True) if prev_td else None
                if actual_value in ("", "&nbsp;", "-"):
                    actual_value = None
                if forecast_value in ("", "&nbsp;", "-"):
                    forecast_value = None
                if previous_value in ("", "&nbsp;", "-"):
                    previous_value = None
                is_released = actual_value is not None

                importance = _importance_from_sentiment(row)
                link_tag = event_cell.find("a", href=True)
                link = None
                if link_tag and link_tag.get("href"):
                    href = link_tag["href"].strip()
                    link = f"https://kr.investing.com{href}" if href.startswith("/") else href

                existing = db.query(EconomicCalendar).filter(
                    EconomicCalendar.event_name == event_name,
                    EconomicCalendar.scheduled_time == event_dt,
                ).first()

                if existing:
                    existing.actual_value = actual_value
                    existing.forecast_value = forecast_value
                    existing.previous_value = previous_value
                    existing.is_released = is_released
                    existing.importance = importance
                    if link:
                        existing.link = link
                    existing.updated_at = datetime.now(timezone.utc)
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
                        category="general",
                        importance=importance,
                        scheduled_time=event_dt,
                        actual_value=actual_value,
                        forecast_value=forecast_value,
                        previous_value=previous_value,
                        is_released=is_released,
                        link=link,
                        source="investing.com",
                    )
                    db.add(cal)
                updated += 1
            except Exception as ex:
                continue

        db.commit()
        print(f"[CALENDAR] Updated {updated} events from kr.investing.com/economic-calendar")

    except Exception as e:
        print(f"[CALENDAR] Error: {e}")
        db.rollback()
    finally:
        db.close()
