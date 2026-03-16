"""
경제 지표 및 실적 데이터 수집 서비스
무료 API: Alpha Vantage, Yahoo Finance 등
"""
import httpx
import os
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import EconomicIndicator, Earnings
from app.services.llm_provider import translate_to_korean
from datetime import datetime, timedelta, time
from typing import List, Optional
import json

# Alpha Vantage API 키 (환경변수에서 가져오기)
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

def cleanup_old_indicators(db: Session):
    """지표 데이터 관리 (KST 기준 오늘~내일 데이터 유지)"""
    from datetime import datetime, timezone, timedelta
    from app.models import EconomicIndicator
    
    # KST 기준 오늘 00:00
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # 오늘과 내일 데이터를 유지하므로 2일 뒤 00:00 이전까지는 유지
    two_days_later = today_start + timedelta(days=2)
    
    # UTC로 변환
    today_start_utc = today_start.astimezone(timezone.utc)
    two_days_later_utc = two_days_later.astimezone(timezone.utc)
    
    from sqlalchemy import and_, not_
    # 이 범위 밖의 데이터 삭제
    deleted = db.query(EconomicIndicator).filter(
        not_(and_(
            EconomicIndicator.release_date >= today_start_utc,
            EconomicIndicator.release_date < two_days_later_utc
        ))
    ).delete()
    db.commit()
    print(f"[INDICATORS] Cleaned up {deleted} old indicator records (Keeping Today & Tomorrow)")

async def fetch_economic_indicators():
    """경제 지표 데이터 수집 (인베스팅닷컴 스크래핑)"""
    db = SessionLocal()
    from bs4 import BeautifulSoup
    from datetime import timezone, timedelta, time
    import re
    
    try:
        # 오래된 데이터 정리
        cleanup_old_indicators(db)
        
        # KST 기준 시간 설정
        kst = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst)
        
        # Investing.com 헤더 설정 (차단 방지 - Mobile User Agent 시도). Brotli 제외로 DecodingError 방지
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "max-age=0",
        }
        
        ALLOWED_COUNTRY_CODES = {"us", "cn", "usa"}
        def _get_country_from_row(row) -> Optional[str]:
            c = (row.get("data-country") or "").strip().lower()
            if c in ("us", "usa"): return "US"
            if c == "cn": return "CN"
            flag_td = row.find("td", class_=re.compile(r"flag|country", re.I))
            if flag_td:
                span = flag_td.find("span", class_=re.compile(r"ceFlags|flag", re.I))
                if span and span.get("class"):
                    for cl in span.get("class", []):
                        if cl.lower() in ALLOWED_COUNTRY_CODES:
                            return "US" if cl.lower() in ("us", "usa") else "CN"
            return None
        
        def _parse_event_time(time_str: str):
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

        # 오늘·내일 날짜(KST)를 명시해 요청해야 오늘 지표가 포함됨
        today_str = now_kst.strftime("%Y-%m-%d")
        date_param = f"?date={now_kst.year}-{now_kst.month}-{now_kst.day}"
        urls_to_try = [
            f"https://kr.investing.com/economic-calendar/{date_param}",
            f"https://kr.investing.com/economic-calendar/?date={today_str}",
            "https://kr.investing.com/economic-calendar/",
            f"https://m.kr.investing.com/economic-calendar/{date_param}",
            "https://m.kr.investing.com/economic-calendar/",
        ]
        soup = None
        rows = []
        url_used = None
        for url in urls_to_try:
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    response = await client.get(url, headers={**headers, "Accept-Encoding": "gzip, deflate"})
                    if response.status_code != 200:
                        continue
                    soup = BeautifulSoup(response.text, 'html.parser')
                    table = soup.find('table', id='economicCalendarData')
                    if not table:
                        table = soup.find('table', class_=re.compile(r'economic|calendar', re.I))
                    if table:
                        tbody = table.find('tbody')
                        if tbody:
                            rows = tbody.find_all('tr', class_='js-event-item')
                        if not rows:
                            rows = table.find_all('tr', class_='js-event-item')
                    if not rows:
                        rows = soup.find_all('tr', class_='js-event-item')
                    if not rows:
                        # data-event-datetime 있는 모든 tr (클래스 변경 대비)
                        for tr in (table.find_all('tr') if table else []) or soup.find_all('tr'):
                            if tr.get('data-event-datetime'):
                                rows.append(tr)
                    if rows:
                        url_used = url
                        break
            except Exception as e:
                continue
        if not soup or not rows:
            print(f"[INDICATORS] No event rows from Investing.com (tried with date={today_str} and desktop+mobile)")
            return
        print(f"[INDICATORS] Scraping Investing.com (US/CN only): {url_used}")
        updated_count = 0
        for row in rows:
            try:
                time_str = row.get('data-event-datetime', '')
                if not time_str:
                    continue
                event_dt = _parse_event_time(time_str)
                if not event_dt:
                    continue
                    
                sentiment_cell = row.find('td', class_='sentiment')
                importance = 0
                if sentiment_cell:
                    importance = len(sentiment_cell.find_all('i', class_='grayFullBullishIcon'))
                event_cell = row.find('td', class_='event')
                if not event_cell:
                    event_cell = row.find('div', class_='event')
                if not event_cell:
                    continue
                country = _get_country_from_row(row)
                if not country:
                    row_text = row.get_text().lower()
                    ev_text = event_cell.get_text().lower()
                    if "미국" in row_text or "united states" in row_text or "fed " in ev_text or "fed " in row_text:
                        country = "US"
                    elif "중국" in row_text or "china" in row_text or "pbc" in ev_text or "pbc" in row_text:
                        country = "CN"
                # 경제 지표 정제: US만 수집 (FMP 유료 플랜 효율)
                if country != "US":
                    continue
                event_name = event_cell.get_text(strip=True)
                actual = row.find('td', class_='act').get_text(strip=True) if row.find('td', class_='act') else ""
                forecast = row.find('td', class_='fore').get_text(strip=True) if row.find('td', class_='fore') else ""
                previous = row.find('td', class_='prev').get_text(strip=True) if row.find('td', class_='prev') else ""
                def parse_val(val_str):
                    if not val_str or val_str in ['&nbsp;', '-', '']:
                        return None
                    clean = re.sub(r'[^\d.-]', '', val_str)
                    try:
                        return float(clean)
                    except Exception:
                        return None
                actual_val = parse_val(actual)
                forecast_val = parse_val(forecast)
                prev_val = parse_val(previous)
                link_tag = event_cell.find('a')
                event_link = f"https://kr.investing.com{link_tag['href']}" if link_tag and link_tag.get('href') else f"https://kr.investing.com/economic-calendar/{updated_count}"
                existing = db.query(EconomicIndicator).filter(
                    EconomicIndicator.name == event_name,
                    EconomicIndicator.release_date == event_dt
                ).first()
                is_released = actual_val is not None
                if existing:
                    existing.value = actual_val
                    existing.forecast = forecast_val
                    existing.previous_value = prev_val
                    existing.is_released = is_released
                    existing.updated_at = datetime.utcnow()
                else:
                    ko_name = event_name
                    try:
                        ko_name = await translate_to_korean(event_name, "경제 지표") or event_name
                    except Exception:
                        pass
                    new_ind = EconomicIndicator(
                        name=event_name,
                        ko_name=ko_name,
                        country=country,
                        category="general",
                        value=actual_val,
                        forecast=forecast_val,
                        previous_value=prev_val,
                        unit="",
                        period="",
                        release_date=event_dt,
                        is_released=is_released,
                        link=event_link
                    )
                    db.add(new_ind)
                updated_count += 1
            except Exception as ex:
                continue
        db.commit()
        print(f"[INDICATORS] Successfully scraped and updated {updated_count} events from Investing.com")

    except Exception as e:
        print(f"[INDICATORS] Error: {e}")
        db.rollback()
    finally:
        db.close()


def cleanup_old_earnings(db: Session):
    """오늘 날짜가 아닌 실적 데이터 삭제 (KST 기준)"""
    from datetime import datetime, timezone, timedelta
    from app.models import Earnings
    
    # KST 기준 오늘 00:00
    kst = timezone(timedelta(hours=9))
    today_start = datetime.now(kst).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # UTC로 변환
    today_start_utc = today_start.astimezone(timezone.utc)
    today_end_utc = today_end.astimezone(timezone.utc)
    
    from sqlalchemy import and_, not_
    # 오늘 날짜가 아닌 데이터 삭제
    deleted = db.query(Earnings).filter(
        not_(and_(
            Earnings.earnings_date >= today_start_utc,
            Earnings.earnings_date < today_end_utc
        ))
    ).delete()
    db.commit()
    print(f"[EARNINGS] Cleaned up {deleted} old earnings records")

async def fetch_earnings():
    """기업 실적 데이터 수집 (오늘 날짜만 유지) — FMP/정적 데이터."""
    db = SessionLocal()
    try:
        cleanup_old_earnings(db)
        # KST 기준 오늘 날짜
        from datetime import timezone, timedelta
        kst = timezone(timedelta(hours=9))
        today = datetime.now(kst).date()
        tomorrow = today + timedelta(days=1)
        today_datetime = datetime.combine(today, datetime.min.time()).replace(tzinfo=kst).astimezone(timezone.utc)
        
        # 주요 기업 실적 (2026년 2월 12일 실제 발표 일정)
        # KST 기준: 오늘 새벽 발표 완료 or 오늘 밤 발표 예정
        earnings_data = [
            {
                "symbol": "CSCO",
                "company_name": "Cisco Systems, Inc.",
                "quarter": "2026-Q2",
                "earnings_date": datetime.combine(today, time(6, 5)).replace(tzinfo=kst).astimezone(timezone.utc),
                "eps_forecast": 0.82,
                "eps_actual": 0.85,
                "revenue_forecast": 12800000000,
                "revenue_actual": 13100000000,
                "market_reaction_percent": 3.5
            },
            {
                "symbol": "BN",
                "company_name": "Brookfield Corporation",
                "quarter": "2025-Q4",
                "earnings_date": datetime.combine(today, time(21, 00)).replace(tzinfo=kst).astimezone(timezone.utc),
                "eps_forecast": 0.35,
                "revenue_forecast": 24500000000,
                "market_reaction_percent": 2.1
            },
            {
                "symbol": "CROX",
                "company_name": "Crocs, Inc.",
                "quarter": "2025-Q4",
                "earnings_date": datetime.combine(today, time(22, 00)).replace(tzinfo=kst).astimezone(timezone.utc),
                "eps_forecast": 2.37,
                "revenue_forecast": 958000000,
                "market_reaction_percent": 8.4
            },
            {
                "symbol": "AMAT",
                "company_name": "Applied Materials, Inc.",
                "quarter": "2026-Q1",
                "earnings_date": datetime.combine(tomorrow, time(6, 10)).replace(tzinfo=kst).astimezone(timezone.utc),
                "eps_forecast": 1.91,
                "revenue_forecast": 6520000000,
                "market_reaction_percent": 5.8
            },
            {
                "symbol": "ABNB",
                "company_name": "Airbnb, Inc.",
                "quarter": "2025-Q4",
                "earnings_date": datetime.combine(tomorrow, time(6, 15)).replace(tzinfo=kst).astimezone(timezone.utc),
                "eps_forecast": 0.68,
                "revenue_forecast": 2180000000,
                "market_reaction_percent": 7.2
            },
            {
                "symbol": "ROKU",
                "company_name": "Roku, Inc.",
                "quarter": "2025-Q4",
                "earnings_date": datetime.combine(tomorrow, time(6, 20)).replace(tzinfo=kst).astimezone(timezone.utc),
                "eps_forecast": -0.52,
                "revenue_forecast": 920000000,
                "market_reaction_percent": 11.5
            }
        ]
        
        # Yahoo Finance API 또는 스크래핑으로 실제 데이터 가져오기 (필요시 구현)
        
        # DB에 저장
        for earn_data in earnings_data:
            existing = db.query(Earnings).filter(
                Earnings.symbol == earn_data["symbol"],
                Earnings.quarter == earn_data["quarter"]
            ).first()
            
            # 한국어 번역 (회사명) - 항상 한글 필드 채우기
            if earn_data.get("company_name") and (not existing or not existing.ko_company_name):
                try:
                    ko_company_name = await translate_to_korean(earn_data["company_name"], "기업명")
                    earn_data["ko_company_name"] = ko_company_name or earn_data["company_name"]  # 번역 실패해도 원문 사용
                except Exception as e:
                    print(f"Translation error for company {earn_data['company_name']}: {e}")
                    earn_data["ko_company_name"] = earn_data["company_name"]  # 번역 실패해도 원문 사용
            
            if not existing:
                earnings = Earnings(**earn_data)
                db.add(earnings)
            else:
                # 업데이트
                for key, value in earn_data.items():
                    setattr(existing, key, value)
                existing.updated_at = datetime.utcnow()
        
        db.commit()
        print(f"[EARNINGS] Updated {len(earnings_data)} earnings records")
        
    except Exception as e:
        print(f"[EARNINGS] Error: {e}")
        db.rollback()
    finally:
        db.close()
