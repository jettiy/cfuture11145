"""
시그널 규칙 엔진: 방향/확률/진입·손절·목표 = 규칙 + (나중에) 숫자모델.
MVP는 모델 없이 모멘텀/추세/ATR 점수로 p_long 산출 → 점차 학습 모델로 교체 가능.
"""
from typing import Dict, List, Any
import pandas as pd
import numpy as np


def _safe(val: Any, default: float = 0.0) -> float:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def get_indicator_snapshot(df: pd.DataFrame) -> Dict[str, float]:
    """
    최신 봉 기준 기술 지표 스냅샷.
    calculate_indicators()가 적용된 DataFrame을 기대.
    """
    if df is None or df.empty:
        return {}
    row = df.iloc[0]
    close = _safe(row.get("Close"))
    return {
        "close": close,
        "ema5": _safe(row.get("EMA5"), close),
        "ema10": _safe(row.get("EMA10"), close),
        "ema20": _safe(row.get("EMA20"), close),
        "ema50": _safe(row.get("EMA50"), close),
        "ema200": _safe(row.get("EMA200"), close),
        "rsi": _safe(row.get("RSI"), 50.0),
        "macd": _safe(row.get("MACD")),
        "macd_signal": _safe(row.get("MACD_Signal")),
        "macd_hist": _safe(row.get("MACD_Hist")),
        "bb_upper": _safe(row.get("BB_Upper"), close),
        "bb_mid": _safe(row.get("BB_Mid"), close),
        "bb_lower": _safe(row.get("BB_Lower"), close),
        "atr": _safe(row.get("ATR"), close * 0.01),
    }


def compute_momentum_score(snap: Dict[str, float]) -> float:
    """
    모멘텀 점수 -1 ~ 1.
    RSI: 30 이하 → 롱 쏠림, 70 이상 → 숏 쏠림.
    MACD Hist: 양수 → 상승 모멘텀, 음수 → 하락 모멘텀.
    """
    rsi = snap.get("rsi", 50.0)
    macd_hist = snap.get("macd_hist", 0.0)
    # RSI: (50 - rsi) / 50 → -1~1 (rsi 0→1, rsi 100→-1)
    rsi_score = (rsi - 50.0) / 50.0  # -1 ~ 1
    # MACD Hist: 부호만 사용해 방향 보정 (스케일은 가격마다 다르므로 정규화)
    macd_sign = np.sign(macd_hist) if macd_hist != 0 else 0
    # 0.6 RSI + 0.4 MACD 방향
    raw = 0.6 * rsi_score + 0.4 * float(macd_sign)
    return max(-1.0, min(1.0, raw))


def compute_trend_score(snap: Dict[str, float]) -> float:
    """
    추세 점수 -1 ~ 1.
    가격이 EMA20 > EMA50 > EMA200 위에 있으면 상승 추세(양수).
    """
    close = snap.get("close", 0.0)
    ema20 = snap.get("ema20", close)
    ema50 = snap.get("ema50", close)
    ema200 = snap.get("ema200", close)
    if close <= 0:
        return 0.0
    # 위쪽 EMA 위에 있을수록 롱 추세
    above_20 = 1.0 if close > ema20 else -1.0
    above_50 = 1.0 if close > ema50 else -1.0
    above_200 = 1.0 if close > ema200 else -1.0
    raw = (above_20 + above_50 + above_200) / 3.0
    return max(-1.0, min(1.0, raw))


def compute_p_long(snap: Dict[str, float], trend_weight: float = 0.5, momentum_weight: float = 0.5) -> float:
    """
    롱 확률 0~100. MVP: 모멘텀 + 추세 점수로만 산출.
    나중에 숫자 모델(예: 로지스틱 회귀, SHAP)로 교체 가능.
    """
    trend = compute_trend_score(snap)
    momentum = compute_momentum_score(snap)
    combined = trend_weight * trend + momentum_weight * momentum  # -1 ~ 1
    # 50 + 50*combined → 0 ~ 100
    p = 50.0 + 50.0 * combined
    return max(0.0, min(100.0, round(p, 1)))


def compute_entry_stop_take(
    current_price: float,
    direction: str,
    atr: float,
    atr_stop_mult: float = 1.5,
    atr_take_mult: float = 2.0,
    min_pct_stop: float = 0.005,
    min_pct_take: float = 0.01,
) -> tuple:
    """
    진입가 = 현재가, 손절/목표 = ATR 기반 (최소 % 보장).
    """
    if atr <= 0 or current_price <= 0:
        atr = current_price * 0.01
    stop_dist = max(atr * atr_stop_mult, current_price * min_pct_stop)
    take_dist = max(atr * atr_take_mult, current_price * min_pct_take)
    if direction == "LONG":
        entry = current_price
        stop_loss = entry - stop_dist
        take_profit = entry + take_dist
    else:
        entry = current_price
        stop_loss = entry + stop_dist
        take_profit = entry - take_dist
    return round(entry, 2), round(stop_loss, 2), round(take_profit, 2)


def build_evidence_list(snap: Dict[str, float], direction: str, p_long: float) -> List[str]:
    """
    LLM 문장화용 근거 리스트 (지표 스냅샷). 여기서는 결정하지 않고 사실만 나열.
    """
    evidence = []
    rsi = snap.get("rsi", 50)
    evidence.append(f"RSI(14)={rsi:.1f}" + (" (과매수 구간)" if rsi > 70 else " (과매도 구간)" if rsi < 30 else " (중립)"))
    evidence.append(f"MACD Histogram={snap.get('macd_hist', 0):.2f}" + (" (상승 모멘텀)" if snap.get("macd_hist", 0) > 0 else " (하락 모멘텀)"))
    close = snap.get("close", 0)
    ema20, ema50 = snap.get("ema20", close), snap.get("ema50", close)
    if close > ema20 and close > ema50:
        evidence.append("가격이 EMA20·EMA50 위에 있어 상승 추세 구간")
    elif close < ema20 and close < ema50:
        evidence.append("가격이 EMA20·EMA50 아래에 있어 하락 추세 구간")
    else:
        evidence.append("가격이 EMA20·50과 엇갈린 혼조 구간")
    bb_mid, bb_upper, bb_lower = snap.get("bb_mid", close), snap.get("bb_upper", close), snap.get("bb_lower", close)
    if close >= bb_upper:
        evidence.append("볼린저 상단 근접 또는 돌파")
    elif close <= bb_lower:
        evidence.append("볼린저 하단 근접 또는 이탈")
    else:
        evidence.append("볼린저 밴드 중앙 부근")
    evidence.append(f"ATR(14)={snap.get('atr', 0):.2f} (변동성)")
    evidence.append(f"규칙 엔진 결과: {direction} 쏠림, 롱 확률 {p_long:.1f}%")
    return evidence


def compute_signal_from_rules(
    chart_data: pd.DataFrame,
    current_price: float,
) -> Dict[str, Any]:
    """
    규칙만으로 시그널 수치 결정. rationale/strategy_title은 상위에서 LLM 문장화 후 채움.
    반환: direction, probability, entry_price, take_profit, stop_loss, risk_reward,
          strategy_title(기본), evidence_list(LLM 입력용).
    """
    from app.services.chart_data_service import calculate_indicators

    if chart_data is None or chart_data.empty:
        raise ValueError("차트 데이터가 없습니다.")
    df = calculate_indicators(chart_data)
    snap = get_indicator_snapshot(df)
    if not snap:
        raise ValueError("지표 스냅샷을 계산할 수 없습니다.")

    p_long = compute_p_long(snap)
    direction = "LONG" if p_long >= 50.0 else "SHORT"
    probability = p_long if direction == "LONG" else 100.0 - p_long
    entry, stop_loss, take_profit = compute_entry_stop_take(
        current_price,
        direction,
        snap.get("atr", current_price * 0.01),
    )

    if direction == "LONG":
        rr = (take_profit - entry) / (entry - stop_loss) if entry > stop_loss else 1.0
    else:
        rr = (entry - take_profit) / (stop_loss - entry) if stop_loss > entry else 1.0
    risk_reward = round(max(0.5, min(5.0, rr)), 2)

    evidence_list = build_evidence_list(snap, direction, p_long)

    return {
        "direction": direction,
        "probability": round(probability, 1),
        "entry_price": entry,
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "risk_reward": risk_reward,
        "strategy_title": f"Rule-MomentumTrend ({direction})",
        "rationale": "",  # 상위에서 LLM 문장화로 채움
        "evidence_list": evidence_list,
        "indicator_snapshot": snap,
    }
