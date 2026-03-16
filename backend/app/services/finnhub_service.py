"""
Finnhub API를 사용한 금융 데이터 수집 서비스
- 뉴스 (메인)
- 캔들/시세 (정식 API, yfinance fallback)
- 기업 실적
"""
import finnhub
import os
import asyncio
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import News, EconomicIndicator, Earnings, EconomicCalendar
from app.services.llm_provider import translate_to_korean
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, Dict, Any
import httpx
import pandas as pd
import logging

logger = logging.getLogger(__name__)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
FINNHUB_ECONOMIC_CALENDAR_URL = "https://finnhub.io/api/v1/calendar/economic"

# Finnhub 캔들 지원 심볼 (TradingView 심볼 -> Finnhub symbol). 비어 있으면 해당 심볼은 yfinance 사용.
# 선물(NQ1!, HSI1! 등)은 Finnhub stock_candles 미지원이므로 제외. 주식/ETF 추가 시 여기에 매핑.
FINNHUB_CANDLE_SYMBOL_MAP = {
    # "NQ1!": "QQQ",  # 선물 대신 ETF 사용 시
}

# resolution: 1, 5, 15, 60, D (Finnhub)
FINNHUB_RESOLUTION_MAP = {
    "1": "1", "5": "5", "15": "15", "30": "15", "1H": "60", "1D": "D", "1W": "D", "1M": "D",
}

def get_finnhub_client():
    """Finnhub 클라이언트 생성"""
    if not FINNHUB_API_KEY:
        return None
    return finnhub.Client(api_key=FINNHUB_API_KEY)


def _parse_finnhub_event_time(date_str: str, time_str: Optional[str], country: str) -> Optional[datetime]:
    """
    Finnhub는 날짜(YYYY-MM-DD)와 시간(예: 13:30)을 주며, 보통 미국 현지 시간 기준일 수 있음.
    여기서는 UTC로 가정하고 파싱하며, time이 없으면 12:00 UTC로 설정.
    """
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d")
        if time_str and str(time_str).strip():
            t = str(time_str).strip()
            if ":" in t:
                parts = t.split(":")
                hour = int(parts[0]) if parts[0].isdigit() else 12
                minute = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                dt = dt.replace(hour=min(hour, 23), minute=min(minute, 59), second=0, microsecond=0)
            else:
                dt = dt.replace(hour=12, minute=0, second=0, microsecond=0)
        else:
            dt = dt.replace(hour=12, minute=0, second=0, microsecond=0)
        return dt.replace(tzinfo=timezone.utc)
    except Exception as e:
        logger.warning("[FINNHUB] parse event time failed date=%s time=%s: %s", date_str, time_str, e)
        return None


def _normalize_economic_event(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Finnhub 경제 캘린더 항목을 EconomicCalendar DB/내부 포맷으로 매핑"""
    try:
        date_str = raw.get("date") or raw.get("day")
        time_str = raw.get("time") or raw.get("hour")
        country = (raw.get("country") or "US").strip() or "US"
        if country.upper() in ("USA", "UNITED STATES"):
            country = "US"
        event_name = (raw.get("event") or raw.get("name") or "").strip()
        if not event_name:
            return None
        scheduled = _parse_finnhub_event_time(date_str, time_str, country)
        if not scheduled:
            return None
        actual = raw.get("actual")
        estimate = raw.get("estimate") or raw.get("forecast")
        previous = raw.get("previous")
        actual_value = str(actual).strip() if actual is not None and str(actual).strip() else None
        forecast_value = str(estimate).strip() if estimate is not None and str(estimate).strip() else None
        previous_value = str(previous).strip() if previous is not None and str(previous).strip() else None
        importance = "medium"
        impact = raw.get("impact") or raw.get("importance")
        if impact is not None:
            if isinstance(impact, str) and impact.lower() in ("high", "critical"):
                importance = "high"
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
            "source": "Finnhub",
            "is_released": actual is not None,
            "link": raw.get("link"),
        }
    except Exception as e:
        logger.warning("[FINNHUB] normalize economic event failed: %s", e)
        return None


async def get_economic_calendar(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Finnhub 경제 캘린더 API 호출.
    https://finnhub.io/api/v1/calendar/economic
    - 국가 필터: US만 요청 (무료 플랜 403 방지).
    - 기간: 오늘 기준 전후 7일만 요청.
    from_date, to_date: YYYY-MM-DD. 미지정 시 오늘-7일 ~ 오늘+7일.
    반환: EconomicCalendar에 upsert 가능한 dict 리스트 (scheduled_time은 datetime UTC).
    """
    api_key = os.getenv("FINNHUB_API_KEY", "") or FINNHUB_API_KEY
    if not (api_key and api_key.strip()):
        logger.warning("[FINNHUB] FINNHUB_API_KEY not set, economic calendar skipped")
        print("[FINNHUB] FINNHUB_API_KEY not set, economic calendar skipped")
        return []
    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()
    # 요청 범위: 오늘 기준 전후 7일만 (너무 먼 미래/과거 조회 시 403 가능)
    if not from_date:
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    if not to_date:
        to_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    # 국가 필터 최소화: US만 요청 (여러 country 시 403 발생 가능)
    params = {"from": from_date, "to": to_date, "token": api_key.strip(), "country": "US"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(FINNHUB_ECONOMIC_CALENDAR_URL, params=params)
            if r.status_code != 200:
                body_preview = (r.text or "")[:400]
                logger.error(
                    "[FINNHUB] economic calendar HTTP status=%s body=%s",
                    r.status_code,
                    body_preview,
                )
                print(
                    f"[FINNHUB] economic calendar HTTP error: status={r.status_code} (from={from_date} to={to_date} country=US). "
                    f"Body: {body_preview}"
                )
                if r.status_code == 403:
                    print("[FINNHUB] 403 Forbidden: free tier limit or invalid country/range. Using country=US and 7-day range only.")
                return []
            data = r.json()
        raw_list = []
        if isinstance(data, list):
            raw_list = data
        elif isinstance(data, dict):
            raw_list = data.get("economicCalendar") or data.get("data") or data.get("events") or []
        print(f"[DEBUG-1] Finnhub에서 받은 원본 데이터 개수: {len(raw_list)}")
        if not raw_list:
            top_keys = list(data.keys())[:10] if isinstance(data, dict) else "n/a"
            logger.info(
                "[FINNHUB] economic calendar API returned 200 but no events: from=%s to=%s country=US response_keys=%s",
                from_date,
                to_date,
                top_keys,
            )
            print(
                f"[FINNHUB] economic calendar empty: from={from_date} to={to_date} country=US. "
                f"Response type={type(data).__name__} keys={top_keys if isinstance(data, dict) else 'list'}"
            )
            return []
        normalized = []
        for item in raw_list:
            n = _normalize_economic_event(item)
            if n:
                normalized.append(n)
        if not normalized:
            logger.warning(
                "[FINNHUB] economic calendar raw=%s but normalized=0 (parsing failed or all filtered): from=%s to=%s",
                len(raw_list),
                from_date,
                to_date,
            )
            print(
                f"[FINNHUB] economic calendar: API returned {len(raw_list)} raw events but 0 normalized (parsing/filter failed). from={from_date} to={to_date}"
            )
            return []
        logger.info(
            "[FINNHUB] economic calendar from=%s to=%s country=US raw=%s normalized=%s",
            from_date,
            to_date,
            len(raw_list),
            len(normalized),
        )
        print(f"[FINNHUB] economic calendar fetched: raw={len(raw_list)} normalized={len(normalized)} (country=US)")
        return normalized
    except httpx.RequestError as e:
        logger.exception("[FINNHUB] economic calendar request error: %s", e)
        print(f"[FINNHUB] economic calendar request error: {e}")
        return []
    except Exception as e:
        logger.exception("[FINNHUB] economic calendar error: %s", e)
        print(f"[FINNHUB] economic calendar error: {e}")
        return []


async def fetch_finnhub_news():
    """Finnhub에서 금융 뉴스 수집"""
    db = SessionLocal()
    try:
        if not FINNHUB_API_KEY:
            print("[FINNHUB] API key not set, skipping news fetch")
            return
        
        client = get_finnhub_client()
        if not client:
            return
        
        # 주요 종목 심볼들
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA"]
        
        for symbol in symbols:
            try:
                # 각 종목별 뉴스 가져오기
                news_list = client.company_news(symbol, _from=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'), to=datetime.now().strftime('%Y-%m-%d'))
                
                for item in news_list[:10]:  # 최신 10개
                    # 중복 체크
                    existing = db.query(News).filter(
                        News.original_link == item.get('url', '')
                    ).first()
                    if existing:
                        continue
                    
                    # Breaking/중요도 판단
                    title_lower = item.get('headline', '').lower()
                    is_breaking = any(keyword in title_lower for keyword in [
                        "breaking", "urgent", "alert", "emergency", "crisis",
                        "crash", "surge", "plunge", "rally", "flash"
                    ])
                    importance = "normal"
                    if is_breaking:
                        importance = "critical"
                    elif any(keyword in title_lower for keyword in [
                        "fed", "federal reserve", "interest rate", "inflation", "cpi",
                        "gdp", "employment", "unemployment", "nfp"
                    ]):
                        importance = "high"
                    
                    # 발행 시간 파싱
                    published_at = None
                    if item.get('datetime'):
                        try:
                            published_at = datetime.fromtimestamp(item['datetime'], tz=timezone.utc)
                        except:
                            published_at = datetime.utcnow()
                    else:
                        published_at = datetime.utcnow()
                    
                    # 뉴스 저장 (원문만, 번역은 비동기)
                    news = News(
                        original_title=item.get('headline', ''),
                        original_summary=item.get('summary', '')[:500],
                        original_link=item.get('url', ''),
                        is_breaking=is_breaking,
                        importance=importance,
                        source=f"Finnhub ({symbol})",
                        published_at=published_at
                    )
                    db.add(news)
                    db.commit()
                    db.refresh(news)
                    try:
                        from app.services.news_service import _broadcast_news, translate_news_in_background
                        _broadcast_news(news)
                        asyncio.create_task(translate_news_in_background(news.id))
                    except Exception as e:
                        print(f"[FINNHUB] Broadcast/translate task error: {e}")
                
            except Exception as e:
                print(f"Error fetching Finnhub news for {symbol}: {e}")
                continue
        
        print(f"[FINNHUB] Fetched news from Finnhub")
        
    except Exception as e:
        print(f"[FINNHUB] Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

async def fetch_finnhub_economic_data():
    """Finnhub에서 경제 지표 및 캘린더 데이터 수집"""
    db = SessionLocal()
    try:
        if not FINNHUB_API_KEY:
            print("[FINNHUB] API key not set, skipping economic data fetch")
            return
        
        client = get_finnhub_client()
        if not client:
            return
        
        # KST 기준 오늘 날짜
        kst = timezone(timedelta(hours=9))
        today = datetime.now(kst).date()
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=kst)
        today_end = today_start + timedelta(days=1)
        
        # Finnhub Economic Calendar API 호출
        # 참고: Finnhub에는 economic_calendar 메서드가 없을 수 있음
        # 대신 일반 뉴스에서 경제 이벤트를 추출하거나, 다른 소스 사용
        try:
            # Finnhub에는 경제 캘린더 API가 없을 수 있으므로
            # 일반 뉴스에서 경제 관련 키워드로 필터링하거나
            # 예시 데이터와 함께 사용
            # 실제 구현 시 TradingEconomics나 다른 API 사용 고려
            print("[FINNHUB] Economic calendar API not available, using alternative method")
            
            # 대안: 주요 경제 뉴스에서 이벤트 추출
            economic_keywords = ["FOMC", "CPI", "GDP", "NFP", "unemployment", "interest rate", "Fed"]
            economic_news = []
            
            for keyword in economic_keywords[:3]:  # 상위 3개 키워드만
                try:
                    # 일반 뉴스 검색 (Finnhub에는 경제 캘린더 API가 없을 수 있음)
                    # 대신 주요 경제 뉴스를 가져와서 이벤트로 변환
                    pass
                except:
                    continue
            
            # Finnhub에는 경제 캘린더 API가 없으므로
            # calendar_service.py에서 예시 데이터와 함께 처리
            # 여기서는 경제 지표 데이터만 처리
            print("[FINNHUB] Economic calendar handled by calendar_service.py")
            
            # 경제 지표는 indicators_service.py에서 처리
            # 여기서는 건너뛰고 calendar_service에서 처리하도록 함
            return
        except Exception as e:
            print(f"[FINNHUB] Error fetching economic calendar: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
        
    except Exception as e:
        print(f"[FINNHUB] Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

async def fetch_finnhub_earnings():
    """Finnhub에서 기업 실적 데이터 수집"""
    db = SessionLocal()
    try:
        if not FINNHUB_API_KEY:
            print("[FINNHUB] API key not set, skipping earnings fetch")
            return
        
        client = get_finnhub_client()
        if not client:
            return
        
        # KST 기준 오늘 날짜
        kst = timezone(timedelta(hours=9))
        today = datetime.now(kst).date()
        today_datetime = datetime.combine(today, datetime.min.time()).replace(tzinfo=kst).astimezone(timezone.utc)
        
        # 실적 캘린더 가져오기
        try:
            from_date = today.strftime('%Y-%m-%d')
            to_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
            # symbol 파라미터는 필수입니다. 빈 문자열("")을 전달하면 모든 심볼의 실적을 가져옵니다.
            earnings_calendar = client.earnings_calendar(_from=from_date, to=to_date, symbol="", international=False)
            
            # 응답 형식 확인 (리스트 또는 딕셔너리)
            earnings_list = []
            if isinstance(earnings_calendar, list):
                earnings_list = earnings_calendar
            elif isinstance(earnings_calendar, dict):
                earnings_list = earnings_calendar.get('earningsCalendar', []) or earnings_calendar.get('data', [])
            
            for earning in earnings_list[:20]:
                # 오늘 날짜인지 확인
                earning_date_str = earning.get('date', '')
                if not earning_date_str:
                    continue
                
                try:
                    earning_date = datetime.strptime(earning_date_str, '%Y-%m-%d').date()
                    earning_date_kst = datetime.combine(earning_date, datetime.min.time()).replace(tzinfo=kst)
                    
                    if earning_date_kst.date() != today:
                        continue
                except:
                    continue
                
                symbol = earning.get('symbol', '')
                if not symbol:
                    continue
                
                # 중복 체크
                existing = db.query(Earnings).filter(
                    Earnings.symbol == symbol,
                    Earnings.earnings_date == earning_date_kst.astimezone(timezone.utc)
                ).first()
                
                if existing:
                    continue
                
                # 한국어 회사명 번역
                ko_company_name = None
                company_name = earning.get('name', '')
                if company_name:
                    try:
                        ko_company_name = await translate_to_korean(company_name, "기업명")
                    except:
                        pass
                
                earnings = Earnings(
                    symbol=symbol,
                    company_name=company_name,
                    ko_company_name=ko_company_name,
                    quarter=earning.get('quarter', ''),
                    earnings_date=earning_date_kst.astimezone(timezone.utc),
                    eps_forecast=earning.get('epsEstimate'),
                    revenue_forecast=earning.get('revenueEstimate'),
                    is_after_hours=earning.get('hour', '').lower() == 'after hours',
                    source="Finnhub"
                )
                db.add(earnings)
            
            db.commit()
            print(f"[FINNHUB] Fetched earnings data")
            
        except Exception as e:
            print(f"[FINNHUB] Error fetching earnings: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
        
    except Exception as e:
        print(f"[FINNHUB] Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


async def fetch_finnhub_candles(
    symbol: str,
    timeframe: str,
    period_days: int = 60,
) -> Optional[pd.DataFrame]:
    """
    Finnhub 정식 API로 캔들 데이터 조회. (시세 메인 소스)
    지원 심볼만 사용하고, 미지원 시 None 반환 → chart_data_service에서 yfinance fallback.
    """
    if not FINNHUB_API_KEY or symbol not in FINNHUB_CANDLE_SYMBOL_MAP:
        return None
    fh_symbol = FINNHUB_CANDLE_SYMBOL_MAP[symbol]
    res = FINNHUB_RESOLUTION_MAP.get(timeframe, "D")
    to_ts = int(datetime.now(timezone.utc).timestamp())
    from_ts = to_ts - (period_days * 86400)
    try:
        def _call():
            client = get_finnhub_client()
            if not client:
                return None
            data = client.stock_candles(fh_symbol, res, from_ts, to_ts)
            if not data or data.get("s") == "no_data" or not data.get("t"):
                return None
            df = pd.DataFrame({
                "Datetime": [datetime.fromtimestamp(t, tz=timezone.utc) for t in data["t"]],
                "Open": data["o"], "High": data["h"], "Low": data["l"], "Close": data["c"], "Volume": data.get("v", [0] * len(data["t"])),
            })
            df = df.sort_values("Datetime", ascending=False)
            return df
        return await asyncio.to_thread(_call)
    except Exception as e:
        print(f"[FINNHUB] Candles error for {symbol}: {e}")
        return None
