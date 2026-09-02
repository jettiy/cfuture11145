"""
시그널 분석: 시그널(방향/확률/진입·손절·목표) = 규칙+숫자모델, 이유(문장) = LLM 문장화만.
API 키는 환경 변수(Cloudflare Secrets 등)로만 주입. .env 직접 읽기 금지.
"""
import asyncio
import httpx
import os
from typing import Dict, Optional, List
from app.services.chart_data_service import fetch_chart_data, calculate_indicators
from app.services.signal_rule_engine import compute_signal_from_rules
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import EconomicCalendar, News
from datetime import datetime, timezone, timedelta


def _load_api_config():
    """환경 변수에서만 API 설정 로드 (Cloudflare Secrets / 시스템 환경변수)"""
    api_key = os.getenv("LLM_API_KEY", "")
    api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    return api_key, api_url, model


# 심볼/타임프레임 한글명 (로깅·LLM 문맥용)
SYMBOL_NAMES = {"NQ1!": "나스닥 선물", "HSI1!": "항셍 선물", "GOLD": "골드 선물", "CL1!": "원유 선물"}
TIMEFRAME_NAMES = {"1": "1분봉", "5": "5분봉", "15": "15분봉", "30": "30분봉", "1H": "60분봉", "1D": "일봉", "1W": "주봉", "1M": "월봉"}


def _get_recent_news(db: Session, limit: int = 15) -> List[str]:
    """실시간 시장 뉴스 헤드라인 조회 (최근 2시간, 상위 limit건)."""
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=2)
        rows = (
            db.query(News)
            .filter(News.created_at >= since)
            .order_by(News.created_at.desc())
            .limit(limit)
            .all()
        )
        return [f"{r.ko_title or r.original_title} ({r.source or '뉴스'})" for r in rows if (r.ko_title or r.original_title)]
    except Exception as e:
        print(f"[SIGNAL_ANALYSIS] News fetch error: {e}")
        return []


async def _llm_verbalize_evidence(
    evidence_list: List[str],
    symbol: str,
    timeframe: str,
    news_headlines: Optional[List[str]] = None,
    fmp_technical_facts: Optional[str] = None,
) -> tuple[str, float]:
    """
    근거 리스트 + FMP 실시간 기술지표 Fact + 뉴스를 LLM에 넘겨 문장화.
    LLM은 반드시 FMP에서 가져온 실시간 수치를 직접 인용해서 설명해야 함.
    Returns: (rationale_text, llm_cost).
    """
    api_key, api_url, model = _load_api_config()
    if not api_key:
        return "\n".join(evidence_list), 0.0

    bullet = "\n".join(f"- {e}" for e in evidence_list)
    system = """주어진 [FMP 실시간 기술지표 Fact]와 실시간 뉴스·기술 근거를 참고하여, 3~5문장의 간결한 한국어 설명을 작성하세요.
**필수**: FMP에서 가져온 실시간 수치(RSI, MACD, EMA 등)를 반드시 직접 인용하여, 그 수치를 근거로 판단한 이유를 설명하세요.
뉴스와 기술적 근거를 바탕으로 판단한 이유만 정리해 문장화하세요. 방향(롱/숏)이나 확률을 새로 추론·결정하지 마세요.
다른 텍스트나 제목 없이 설명 문단만 반환하세요."""

    news_block = ""
    if news_headlines:
        news_block = "\n[실시간 시장 뉴스]\n" + "\n".join(f"- {h}" for h in news_headlines) + "\n\n"

    fmp_block = ""
    if fmp_technical_facts and fmp_technical_facts.strip():
        fmp_block = "\n" + fmp_technical_facts.strip() + "\n\n"

    user = f"""다음은 {symbol} {timeframe} 차트 분석을 위한 정보입니다. FMP 실시간 기술지표 Fact와 뉴스·근거를 참고해, **위 Fact 수치를 반드시 인용**하여 설명만 작성하세요.
{fmp_block}{news_block}[기술 지표 근거]
{bullet}"""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "temperature": 0.3,
                    "max_tokens": 400,
                },
                timeout=30.0,
            )
            if response.status_code != 200:
                return "\n".join(evidence_list), 0.0
            result = response.json()
            if "choices" not in result or not result["choices"]:
                return "\n".join(evidence_list), 0.0
            content = result["choices"][0]["message"]["content"].strip()
            # 대략 비용 (토큰 추정)
            input_tok = (len(system) + len(user)) / 4
            output_tok = len(content) / 4
            cost = (input_tok / 1_000_000 * 0.25) + (output_tok / 1_000_000 * 0.38)
            return content, round(cost, 6)
    except Exception:
        return "\n".join(evidence_list), 0.0


async def analyze_signal_with_llm(
    symbol: str,
    timeframe: str,
    lookahead_n: int = 30,
    db: Optional[Session] = None,
) -> Dict:
    """
    시그널 = 규칙 엔진(모멘텀/추세/ATR)으로 결정.
    이유(문장) = 근거 리스트를 LLM이 문장화만 (선택). LLM 없으면 근거 목록을 그대로 rationale로 사용.
    """
    print(f"[SIGNAL_ANALYSIS] Fetching chart data for {symbol} ({timeframe})...")
    chart_data = None
    for attempt in range(1, 4):
        chart_data = await fetch_chart_data(symbol, timeframe, lookahead_n)
        if chart_data is not None and not chart_data.empty:
            break
        if attempt < 3:
            wait = 2.0 * attempt
            print(f"[SIGNAL_ANALYSIS] Chart data empty/failed (attempt {attempt}/3), retry in {wait}s")
            await asyncio.sleep(wait)
    if chart_data is None or chart_data.empty:
        raise ValueError(f"차트 데이터를 가져올 수 없습니다: {symbol} ({timeframe}). 잠시 후 다시 시도해 주세요.")

    # 선물 실시간가: FMP Commodities API(NQUSD, GCUSD, CLUSD) 우선 사용, 없으면 차트 Close
    current_price = None
    try:
        from app.services.fmp_service import get_fmp_commodity_price
        current_price = await get_fmp_commodity_price(symbol)
    except Exception as e:
        print(f"[SIGNAL_ANALYSIS] FMP commodity price skip: {e}")
    if current_price is None:
        current_price = float(chart_data.iloc[0]["Close"])
    else:
        print(f"[SIGNAL_ANALYSIS] Using FMP commodity price for {symbol}: {current_price}")
    # 규칙 엔진으로 방향/확률/진입·손절·목표 결정
    raw = compute_signal_from_rules(chart_data, current_price)
    evidence_list = raw["evidence_list"]

    # 캘린더 + 실시간 뉴스 문맥
    news_headlines: List[str] = []
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        events = db.query(EconomicCalendar).filter(
            EconomicCalendar.scheduled_time >= today,
            EconomicCalendar.scheduled_time < tomorrow,
            EconomicCalendar.importance.in_(["high", "critical"]),
        ).all()
        if events:
            cal_lines = [f"- {e.scheduled_time.strftime('%H:%M')} {e.ko_event_name or e.event_name}" for e in events]
            evidence_list = evidence_list + ["오늘 주요 일정: " + "; ".join(cal_lines)]
        news_headlines = _get_recent_news(db, limit=15)
    except Exception as e:
        print(f"[SIGNAL_ANALYSIS] Calendar/News fetch error: {e}")
    finally:
        if close_db:
            db.close()

    # FMP 에이전트: 해당 타임프레임 실시간 RSI/MACD/EMA 조회 후 프롬프트에 Fact로 주입
    fmp_facts = ""
    try:
        from app.services.fmp_service import get_fmp_technical_facts
        fmp_facts = await get_fmp_technical_facts(symbol, timeframe)
    except Exception as e:
        print(f"[SIGNAL_ANALYSIS] FMP technical facts skip: {e}")

    # LLM: FMP Fact + 실시간 뉴스 + 근거를 바탕으로 문장화 (FMP 수치 직접 인용 지시)
    rationale, llm_cost = await _llm_verbalize_evidence(
        evidence_list, symbol, timeframe, news_headlines=news_headlines, fmp_technical_facts=fmp_facts or None
    )
    if not rationale.strip():
        rationale = "\n".join(evidence_list)

    out = {
        "direction": raw["direction"],
        "probability": raw["probability"],
        "entry_price": raw["entry_price"],
        "take_profit": raw["take_profit"],
        "stop_loss": raw["stop_loss"],
        "risk_reward": raw["risk_reward"],
        "strategy_title": raw["strategy_title"],
        "rationale": rationale,
        "llm_cost": llm_cost,
    }
    print(f"[SIGNAL_ANALYSIS] Rule signal: {out['direction']} ({out['probability']:.1f}%) - LLM cost: ${llm_cost:.6f}")
    return out
