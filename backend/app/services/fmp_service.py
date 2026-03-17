"""
FMP (Financial Modeling Prep) API — 경제 캘린더 + 시장 뉴스 (100% FMP 단일 소스)
- 경제 캘린더: https://financialmodelingprep.com/stable/economic-calendar
- 뉴스: https://financialmodelingprep.com/stable/fmp-articles
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

FMP_API_KEY = os.getenv("FMP_API_KEY", "")
FMP_ECONOMIC_CALENDAR_URL = "https://financialmodelingprep.com/stable/economic-calendar"
FMP_ARTICLES_URL = "https://financialmodelingprep.com/api/v3/fmp/articles"
FMP_QUOTE_URL = "https://financialmodelingprep.com/api/v3/quote"
FMP_TECHNICAL_INDICATOR_BASE = "https://financialmodelingprep.com/api/v3/technical_indicator"
FMP_STOCK_NEWS_URL = "https://financialmodelingprep.com/api/v3/stock_news"
FMP_KEY_METRICS_URL = "https://financialmodelingprep.com/api/v3/key-metrics-ttm"
FMP_INCOME_STATEMENT_URL = "https://financialmodelingprep.com/api/v3/income-statement"
FMP_EARNINGS_URL = "https://financialmodelingprep.com/api/v3/earnings-surprises"
FMP_SEARCH_NAME_URL = "https://financialmodelingprep.com/stable/search-name"
# 주요 지수 심볼 (FMP: ^GSPC=S&P500, ^IXIC=Nasdaq, ^DJI=Dow)
FMP_INDEX_SYMBOLS = ["^GSPC", "^IXIC", "^DJI"]
# TradingView/앱 심볼 → FMP API 심볼 (나스닥 선물 NQ1!은 NQUSD로 조회해 데이터 없음 해결)
FMP_SYMBOL_MAP = {"NQ1!": "NQUSD", "HSI1!": "^HSI", "GOLD": "GCUSD", "CL1!": "CLUSD"}
# 선물 실시간가: FMP Commodities API (NQUSD, GCUSD, CLUSD) — 유료 플랜
FMP_COMMODITIES_QUOTE_URL = "https://financialmodelingprep.com/stable/quote"
FMP_COMMODITY_SYMBOL_MAP = {"NQ1!": "NQUSD", "GOLD": "GCUSD", "CL1!": "CLUSD"}
# 타임프레임 → FMP interval (technical_indicator)
FMP_INTERVAL_MAP = {"1": "1min", "5": "5min", "15": "15min", "30": "30min", "1H": "1hour", "1D": "daily", "1W": "daily", "1M": "daily"}

# HTTP 기본 헤더 (403/차단 방지에 도움)
_COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Encoding": "gzip, deflate",
}

# 해외선물 트레이더용: 거시/지수/ETF 중심 뉴스만
FMP_FUTURES_NEWS_TICKERS = "SPY,QQQ,DIA,TLT,GLD,USO,UUP"


def _parse_fmp_datetime(date_str: Optional[str], time_str: Optional[str]) -> Optional[datetime]:
    """FMP date/time을 UTC datetime으로 변환."""
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
    """FMP 경제 캘린더 항목 → EconomicCalendar 포맷. event→name, date→scheduled_at(UTC), impact→importance, estimate→forecast, previous→previous, actual→actual."""
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
    FMP 경제 캘린더 API 호출. country=US 인 것만 필터링.
    stable/economic-calendar?from=...&to=...&apikey=...
    반환: EconomicCalendar에 upsert 가능한 dict 리스트 (US만).
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
    # country=US 쿼리 파라미터도 명시(운영에서 불필요 국가 유입 방지) + 로컬 필터 병행
    params = {"from": from_date, "to": to_date, "country": "US", "apikey": api_key}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(FMP_ECONOMIC_CALENDAR_URL, params=params, headers=_COMMON_HEADERS)
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
            if n and n.get("country") == "US":
                normalized.append(n)
        print(f"[FMP Calendar] Successfully parsed {len(normalized)} US events")
        logger.info("[FMP] economic calendar from=%s to=%s US_events=%s", from_date, to_date, len(normalized))
        return normalized
    except httpx.RequestError as e:
        logger.exception("[FMP] economic calendar request error: %s", e)
        print(f"[FMP] economic calendar request error: {e}")
        return []
    except Exception as e:
        logger.exception("[FMP] economic calendar error: %s", e)
        print(f"[FMP] economic calendar error: {e}")
        return []


async def fetch_fmp_news() -> int:
    """
    FMP Stock News API로 시장 뉴스 수집(ETF/거시 중심). News 모델에 맞게 파싱 후 DB Insert.
    - tickers=SPY,QQQ,DIA,TLT,GLD,USO,UUP 로 선물 트레이딩에 불필요한 개별주 뉴스 최소화
    - 403 등 에러 발생 시 서버가 죽지 않도록 안전하게 0 반환
    반환: 새로 저장한 뉴스 개수.
    """
    from app.database import SessionLocal
    from app.models import News

    api_key = (os.getenv("FMP_API_KEY") or FMP_API_KEY or "").strip()
    if not api_key:
        print("[FMP] FMP_API_KEY not set, news fetch skipped")
        return 0
    db = SessionLocal()
    try:
        params = {
            "tickers": FMP_FUTURES_NEWS_TICKERS,
            "limit": 50,
            "apikey": api_key,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            # /api/v3/fmp/articles 는 플랜/권한에 따라 403이 나올 수 있어 stock_news로 통일
            r = await client.get(FMP_STOCK_NEWS_URL, params=params, headers=_COMMON_HEADERS)
        if r.status_code != 200:
            # 403 등은 운영에서 빈번할 수 있으므로 예외로 올리지 않고 로그만 남김
            print(f"[FMP] stock_news HTTP error: status={r.status_code}")
            logger.error("[FMP] stock_news HTTP status=%s body=%s", r.status_code, (r.text or "")[:300])
            return 0
        data = r.json()
        raw_list = data if isinstance(data, list) else (data.get("data") or data.get("content") or data.get("articles") or [])
        if not raw_list:
            print("[FMP] stock_news empty")
            return 0
        # 홍보/광고성 기사 제목 키워드 필터 (FMP 유료 플랜 효율)
        _AD_TITLE_KEYWORDS = [
            "sponsored", "advertisement", "ad ", " ads ", "promotion", "promotional",
            "광고", "프로모션", "무료 체험", "지금 가입", "추천 이벤트", "할인", "배너",
            "subscribe now", "sign up now", "click here", "partner content", "brand voice",
        ]
        def _is_ad_or_promo_title(t: str) -> bool:
            if not t:
                return True
            lower = t.lower().strip()
            return any(kw in lower for kw in _AD_TITLE_KEYWORDS)
        added = 0
        for item in raw_list:
            try:
                title = (item.get("title") or item.get("headline") or item.get("name") or "").strip()
                if not title:
                    continue
                if _is_ad_or_promo_title(title):
                    continue
                link = (item.get("link") or item.get("url") or item.get("publicationUrl") or "").strip()
                if not link:
                    link = "#"
                # stock_news는 "text" / "site" / "publishedDate" 등을 사용
                summary = (item.get("text") or item.get("content") or item.get("snippet") or item.get("summary") or "")[:500]
                source = (item.get("site") or item.get("source") or "FMP").strip()
                pub_at = datetime.now(timezone.utc)
                if item.get("publishedDate") or item.get("date") or item.get("publishedAt") or item.get("published_at"):
                    try:
                        dt_str = str(item.get("publishedDate") or item.get("date") or item.get("publishedAt") or item.get("published_at")).strip()
                        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                            try:
                                pub_at = datetime.strptime(dt_str[:19] if len(dt_str) >= 19 else dt_str[:10], fmt)
                                if pub_at.tzinfo is None:
                                    pub_at = pub_at.replace(tzinfo=timezone.utc)
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass
                existing = db.query(News).filter(News.original_link == link).first()
                if existing:
                    continue
                news = News(
                    original_title=title,
                    original_summary=summary or None,
                    original_link=link,
                    is_breaking=False,
                    importance="normal",
                    sentiment="neutral",
                    source=source,
                    published_at=pub_at,
                )
                db.add(news)
                db.commit()
                db.refresh(news)
                try:
                    from app.services.news_service import _broadcast_news, translate_news_in_background
                    import asyncio
                    _broadcast_news(news)
                    asyncio.create_task(translate_news_in_background(news.id))
                except Exception as _e:
                    logger.debug("[FMP] broadcast/translate skip: %s", _e)
                added += 1
            except Exception as e:
                logger.warning("[FMP] news item save failed: %s", e)
                db.rollback()
                continue
        print(f"[FMP News] Successfully parsed {added} news articles")
        logger.info("[FMP] news added=%s", added)
        return added
    except Exception as e:
        logger.exception("[FMP] news fetch error: %s", e)
        print(f"[FMP] news fetch error: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


async def fetch_fmp_indexes() -> int:
    """
    FMP Quote API로 주요 지수(나스닥, S&P500, 다우) 수집 → IndexData 테이블 Upsert.
    api/v3/quote 사용. 1분마다 스케줄러에서 호출.
    """
    from app.database import SessionLocal
    from app.models import IndexData

    api_key = (os.getenv("FMP_API_KEY") or FMP_API_KEY or "").strip()
    if not api_key:
        print("[FMP] FMP_API_KEY not set, indexes fetch skipped")
        return 0
    symbols_param = ",".join(FMP_INDEX_SYMBOLS)
    url = f"{FMP_QUOTE_URL}/{symbols_param}"
    params = {"apikey": api_key}
    db = SessionLocal()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params)
        if r.status_code != 200:
            print(f"[FMP] quotes HTTP error: status={r.status_code}")
            return 0
        data = r.json()
        raw_list = data if isinstance(data, list) else []
        if not raw_list:
            print("[FMP] quotes empty")
            return 0
        now_utc = datetime.now(timezone.utc)
        upserted = 0
        for item in raw_list:
            try:
                symbol = (item.get("symbol") or "").strip()
                if not symbol:
                    continue
                price = item.get("price")
                if price is not None and not isinstance(price, (int, float)):
                    try:
                        price = float(price)
                    except (TypeError, ValueError):
                        price = None
                change = item.get("change")
                if change is not None and not isinstance(change, (int, float)):
                    try:
                        change = float(change)
                    except (TypeError, ValueError):
                        change = None
                changes_pct = item.get("changesPercentage") or item.get("changes_percentage")
                if changes_pct is not None and not isinstance(changes_pct, (int, float)):
                    try:
                        changes_pct = float(changes_pct)
                    except (TypeError, ValueError):
                        changes_pct = None
                prev_close = item.get("previousClose") or item.get("previous_close")
                if prev_close is not None and not isinstance(prev_close, (int, float)):
                    try:
                        prev_close = float(prev_close)
                    except (TypeError, ValueError):
                        prev_close = None
                name = (item.get("name") or "").strip() or None
                existing = db.query(IndexData).filter(IndexData.symbol == symbol).first()
                if existing:
                    existing.price = price
                    existing.change = change
                    existing.changes_percentage = changes_pct
                    existing.previous_close = prev_close
                    existing.name = name or existing.name
                    existing.updated_at = now_utc
                    existing.source = "FMP"
                else:
                    row = IndexData(
                        symbol=symbol,
                        name=name,
                        price=price,
                        change=change,
                        changes_percentage=changes_pct,
                        previous_close=prev_close,
                        updated_at=now_utc,
                        source="FMP",
                    )
                    db.add(row)
                upserted += 1
            except Exception as e:
                logger.warning("[FMP] index row upsert failed: %s", e)
                db.rollback()
                continue
        db.commit()
        print(f"[FMP Indexes] Successfully upserted {upserted} index quotes")
        logger.info("[FMP] indexes upserted=%s", upserted)
        return upserted
    except Exception as e:
        logger.exception("[FMP] indexes fetch error: %s", e)
        print(f"[FMP] indexes fetch error: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def _fmp_symbol(symbol: str) -> str:
    """앱 심볼을 FMP API용 심볼로 변환."""
    return FMP_SYMBOL_MAP.get(symbol, symbol)


def _fmp_commodity_symbol(symbol: str) -> Optional[str]:
    """앱 선물 심볼 → FMP Commodities API 심볼 (NQUSD, GCUSD, CLUSD). 해당 없으면 None."""
    return FMP_COMMODITY_SYMBOL_MAP.get(symbol)


async def get_fmp_commodity_price(symbol: str) -> Optional[float]:
    """
    FMP Commodities Quote API로 선물 실시간가 조회 (NQUSD, GCUSD, CLUSD).
    앱 심볼 NQ1!, GOLD, CL1!만 지원. 없거나 실패 시 None.
    """
    fmp_sym = _fmp_commodity_symbol(symbol)
    if not fmp_sym:
        return None
    api_key = (os.getenv("FMP_API_KEY") or FMP_API_KEY or "").strip()
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                FMP_COMMODITIES_QUOTE_URL,
                params={"symbol": fmp_sym, "apikey": api_key},
            )
        if r.status_code != 200:
            return None
        data = r.json()
        items = data if isinstance(data, list) else []
        if not items:
            return None
        price = items[0].get("price") or items[0].get("close")
        if price is not None:
            return float(price)
    except Exception as e:
        logger.warning("[FMP] commodity quote error: %s", e)
    return None


async def get_fmp_technical_facts(symbol: str, timeframe: str) -> str:
    """
    FMP Technical Indicators API로 RSI(14), MACD(12,26,9), EMA(20,50,200) 조회.
    LLM 프롬프트에 넣을 'Fact 데이터' 문자열 반환. 실패 시 빈 문자열.
    """
    api_key = (os.getenv("FMP_API_KEY") or FMP_API_KEY or "").strip()
    if not api_key:
        return ""
    fmp_sym = _fmp_symbol(symbol)
    interval = FMP_INTERVAL_MAP.get(timeframe, "daily")
    lines = []
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            # RSI(14)
            r_rsi = await client.get(
                f"{FMP_TECHNICAL_INDICATOR_BASE}/{interval}/{fmp_sym}",
                params={"type": "rsi", "period": 14, "apikey": api_key},
            )
            if r_rsi.status_code == 200:
                data = r_rsi.json()
                if isinstance(data, list) and len(data) > 0:
                    last = data[0]
                    val = last.get("rsi") or last.get("value")
                    if val is not None:
                        lines.append(f"RSI(14) = {val}")
            # EMA 20, 50, 200
            for period in (20, 50, 200):
                r_ema = await client.get(
                    f"{FMP_TECHNICAL_INDICATOR_BASE}/{interval}/{fmp_sym}",
                    params={"type": "ema", "period": period, "apikey": api_key},
                )
                if r_ema.status_code == 200:
                    data = r_ema.json()
                    if isinstance(data, list) and len(data) > 0:
                        val = data[0].get("ema") or data[0].get("value")
                        if val is not None:
                            lines.append(f"EMA({period}) = {val}")
            # MACD(12,26,9)
            r_macd = await client.get(
                f"{FMP_TECHNICAL_INDICATOR_BASE}/{interval}/{fmp_sym}",
                params={"type": "macd", "fast": 12, "slow": 26, "signal": 9, "apikey": api_key},
            )
            if r_macd.status_code == 200:
                data = r_macd.json()
                if isinstance(data, list) and len(data) > 0:
                    d = data[0]
                    macd = d.get("macd") or d.get("macdLine")
                    sig = d.get("macd_signal") or d.get("signalLine")
                    hist = d.get("macd_hist") or d.get("histogram")
                    if macd is not None or sig is not None:
                        parts = [f"MACD(12,26,9): macd={macd}", f"signal={sig}", f"hist={hist}"]
                        lines.append(", ".join(p for p in parts if p.split("=")[-1] not in ("None", "")))
    except Exception as e:
        logger.warning("[FMP] technical facts fetch error: %s", e)
    if not lines:
        return ""
    return "[FMP 실시간 기술지표 Fact]\n" + "\n".join(lines)


async def get_fmp_quote_for_briefing(symbol: str) -> str:
    """FMP Quote 조회 → LLM이 이해하기 쉬운 텍스트로 변환 (MCP 규격 필드 누락 없이)."""
    api_key = (os.getenv("FMP_API_KEY") or FMP_API_KEY or "").strip()
    if not api_key:
        return ""
    fmp_sym = _fmp_symbol(symbol)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{FMP_QUOTE_URL}/{fmp_sym}", params={"apikey": api_key})
        if r.status_code != 200:
            return ""
        data = r.json()
        items = data if isinstance(data, list) else []
        if not items:
            return ""
        d = items[0]
        parts = [
            f"symbol={d.get('symbol')}",
            f"price={d.get('price')}",
            f"change={d.get('change')}",
            f"changesPercentage={d.get('changesPercentage')}",
            f"open={d.get('open')}",
            f"dayHigh={d.get('dayHigh')}",
            f"dayLow={d.get('dayLow')}",
            f"yearHigh={d.get('yearHigh')}",
            f"yearLow={d.get('yearLow')}",
            f"volume={d.get('volume')}",
            f"avgVolume={d.get('avgVolume')}",
            f"previousClose={d.get('previousClose')}",
        ]
        return "[FMP Quote 실시간가]\n" + ", ".join(str(p) for p in parts if p.split("=")[-1] not in ("None", ""))
    except Exception as e:
        logger.warning("[FMP] quote for briefing error: %s", e)
        return ""


async def get_fmp_stock_news_for_briefing(symbol: str, limit: int = 10) -> str:
    """FMP Stock News 조회 → LLM용 텍스트 (title, publishedDate, text 등 누락 없이)."""
    api_key = (os.getenv("FMP_API_KEY") or FMP_API_KEY or "").strip()
    if not api_key:
        return ""
    fmp_sym = _fmp_symbol(symbol)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                FMP_STOCK_NEWS_URL,
                params={"tickers": fmp_sym, "limit": limit, "apikey": api_key},
            )
        if r.status_code != 200:
            return ""
        data = r.json()
        items = data if isinstance(data, list) else []
        if not items:
            return ""
        lines = []
        for i, n in enumerate(items[:limit], 1):
            title = n.get("title") or ""
            published = n.get("publishedDate") or n.get("published_at") or ""
            text = (n.get("text") or n.get("content") or "")[:300]
            url = n.get("url") or ""
            site = n.get("site") or ""
            lines.append(f"[{i}] title={title}; publishedDate={published}; site={site}; text={text}; url={url}")
        return "[FMP 해당 종목 최신 뉴스]\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("[FMP] stock news for briefing error: %s", e)
        return ""


async def get_fmp_key_metrics_for_briefing(symbol: str) -> str:
    """FMP Key Metrics TTM 조회 → LLM용 텍스트 (필드 누락 없이)."""
    api_key = (os.getenv("FMP_API_KEY") or FMP_API_KEY or "").strip()
    if not api_key:
        return ""
    fmp_sym = _fmp_symbol(symbol)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                FMP_KEY_METRICS_URL,
                params={"symbol": fmp_sym, "apikey": api_key},
            )
        if r.status_code != 200:
            return ""
        data = r.json()
        items = data if isinstance(data, list) else []
        if not items:
            return ""
        d = items[0]
        pairs = [f"{k}={v}" for k, v in sorted(d.items()) if v is not None and str(v).strip() != ""]
        return "[FMP Key Metrics 주요 재무지표]\n" + ", ".join(pairs[:30])
    except Exception as e:
        logger.warning("[FMP] key metrics for briefing error: %s", e)
        return ""


async def get_fmp_earnings_for_briefing(symbol: str, limit: int = 4) -> str:
    """FMP Income Statement(분기) + Earnings Surprises 조회 → LLM용 실적/어닝/매출 텍스트."""
    api_key = (os.getenv("FMP_API_KEY") or FMP_API_KEY or "").strip()
    if not api_key:
        return ""
    fmp_sym = _fmp_symbol(symbol)
    lines = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 분기 손익계산서 (최신 분기 실적: 매출, 영업이익, 순이익 등)
            r_inc = await client.get(
                FMP_INCOME_STATEMENT_URL,
                params={"symbol": fmp_sym, "period": "quarter", "limit": limit, "apikey": api_key},
            )
            if r_inc.status_code == 200:
                data = r_inc.json()
                items = data if isinstance(data, list) else []
                for i, d in enumerate(items[:limit], 1):
                    period = d.get("period") or d.get("date", "")[:10]
                    revenue = d.get("revenue")
                    gross_profit = d.get("grossProfit")
                    operating_income = d.get("operatingIncome")
                    net_income = d.get("netIncome")
                    eps = d.get("eps")
                    parts = [f"기간={period}", f"revenue={revenue}", f"grossProfit={gross_profit}",
                             f"operatingIncome={operating_income}", f"netIncome={net_income}", f"eps={eps}"]
                    lines.append(f"[분기{i}] " + ", ".join(str(p) for p in parts if p.split("=")[-1] not in ("None", "")))
            # Earnings Surprises (실적 컨센서스 대비)
            r_sur = await client.get(
                f"{FMP_EARNINGS_URL}/{fmp_sym}",
                params={"apikey": api_key},
            )
            if r_sur.status_code == 200:
                sur_data = r_sur.json()
                sur_list = sur_data if isinstance(sur_data, list) else []
                for s in sur_list[:4]:
                    date = s.get("date") or s.get("fiscalDateEnding", "")
                    actual_eps = s.get("actualEarningResult") or s.get("actualEps")
                    est_eps = s.get("estimatedEarning") or s.get("estimatedEps")
                    surprise = s.get("surprise") or s.get("surprisePercentage")
                    if date or actual_eps is not None:
                        lines.append(f"[어닝서프라이즈] date={date}, actualEps={actual_eps}, estimateEps={est_eps}, surprise={surprise}")
    except Exception as e:
        logger.warning("[FMP] earnings for briefing error: %s", e)
    if not lines:
        return ""
    return "[FMP 실적/어닝/매출]\n" + "\n".join(lines)


async def get_fmp_ticker_by_name(company_name: str) -> Optional[str]:
    """한글/영문 종목명으로 FMP search-name API 호출 후 첫 번째 주식 티커 반환. 없으면 None."""
    api_key = (os.getenv("FMP_API_KEY") or FMP_API_KEY or "").strip()
    if not api_key or not (company_name or "").strip():
        return None
    name = (company_name or "").strip()
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                FMP_SEARCH_NAME_URL,
                params={"query": name, "apikey": api_key},
            )
        if r.status_code != 200:
            return None
        data = r.json()
        items = data if isinstance(data, list) else []
        for it in items:
            sym = (it.get("symbol") or "").strip()
            if not sym:
                continue
            # 지수/ETF 제외, 주식 심볼 우선 (보통 5자 이하 또는 거래소 접미사)
            if sym.startswith("^") or "." not in sym and len(sym) <= 6:
                return sym
        if items:
            return (items[0].get("symbol") or "").strip() or None
    except Exception as e:
        logger.warning("[FMP] search-name error: %s", e)
    return None
