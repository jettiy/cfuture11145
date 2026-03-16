"""
차트 데이터 수집 서비스 — yfinance 단일 소스.
캐시 및 rate limit 회피.
"""
import yfinance as yf
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import pandas as pd
import asyncio
import time

# 캐시: (symbol, timeframe, lookahead_n) -> (fetched_at, df). TTL 초.
_CHART_CACHE: Dict[Tuple[str, str, int], Tuple[float, Optional[pd.DataFrame]]] = {}
_CHART_CACHE_TTL_SEC = 90
_LAST_REQUEST_TIME: Dict[str, float] = {}
# yfinance rate limit 회피: 최소 3초 간격 (Render 무료 환경 고려)
_MIN_REQUEST_INTERVAL_SEC = 3.0

# TradingView 심볼을 Yahoo Finance 심볼로 매핑
SYMBOL_MAPPING = {
    "NQ1!": "NQ=F",  # 나스닥 선물
    "HSI1!": "HSI=F",  # 항셍 선물
    "GOLD": "GC=F",  # 골드 선물
    "CL1!": "CL=F",  # 원유 선물
}

# 타임프레임 매핑 (TradingView 형식 -> yfinance interval)
TIMEFRAME_MAPPING = {
    "1": "1m",      # 1분봉
    "5": "5m",      # 5분봉
    "15": "15m",    # 15분봉
    "30": "30m",    # 30분봉
    "1H": "1h",     # 60분봉
    "1D": "1d",     # 일봉
    "1W": "1wk",    # 주봉
    "1M": "1mo",    # 월봉
}

def get_yahoo_symbol(tradingview_symbol: str) -> str:
    """TradingView 심볼을 Yahoo Finance 심볼로 변환"""
    return SYMBOL_MAPPING.get(tradingview_symbol, tradingview_symbol)

def get_yfinance_interval(timeframe: str) -> str:
    """TradingView 타임프레임을 yfinance interval로 변환"""
    return TIMEFRAME_MAPPING.get(timeframe, "15m")

def get_period_for_timeframe(timeframe: str, lookahead_n: int = 30) -> Tuple[str, int]:
    """
    타임프레임에 따라 적절한 기간(period)과 데이터 포인트 수를 반환
    
    Returns:
        (period, max_results): period는 yfinance period 파라미터, max_results는 최대 데이터 포인트 수
    """
    period_days_map = {
        "1": (7, 10080),      # 1분봉: 최근 7일, 최대 10080개 (7일 * 24시간 * 60분)
        "5": (30, 8640),      # 5분봉: 최근 30일, 최대 8640개
        "15": (60, 5760),     # 15분봉: 최근 60일, 최대 5760개
        "30": (60, 2880),     # 30분봉: 최근 60일, 최대 2880개
        "1H": (730, 17520),   # 60분봉: 최근 2년, 최대 17520개
        "1D": (730, 730),     # 일봉: 최근 2년, 최대 730개
        "1W": (1825, 260),    # 주봉: 최근 5년, 최대 260개
        "1M": (3650, 120),    # 월봉: 최근 10년, 최대 120개
    }
    
    period_days, max_results = period_days_map.get(timeframe, (60, 1000))
    
    # lookahead_n을 고려하여 더 많은 데이터를 가져올 수 있도록 조정
    if lookahead_n > 30:
        period_days = int(period_days * (lookahead_n / 30))
    
    return f"{period_days}d", max_results

def _fetch_chart_data_sync(symbol: str, timeframe: str, lookahead_n: int) -> Optional[pd.DataFrame]:
    """동기 yfinance 호출 (캐시/rate limit 없이 한 번 시도)."""
    yahoo_symbol = get_yahoo_symbol(symbol)
    interval = get_yfinance_interval(timeframe)
    period, max_results = get_period_for_timeframe(timeframe, lookahead_n)
    ticker = yf.Ticker(yahoo_symbol)
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        return None
    df.columns = [col.replace(' ', '') for col in df.columns]
    df.reset_index(inplace=True)
    if 'Date' in df.columns:
        df.rename(columns={'Date': 'Datetime'}, inplace=True)
    required_columns = ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']
    available_columns = [col for col in required_columns if col in df.columns]
    df = df[available_columns]
    df = df.sort_values('Datetime', ascending=False)
    if len(df) > max_results:
        df = df.head(max_results)
    return df


async def fetch_chart_data(
    symbol: str,
    timeframe: str,
    lookahead_n: int = 30,
    max_retries: int = 3,
) -> Optional[pd.DataFrame]:
    """
    차트 데이터: yfinance 사용. 캐시·재시도 적용.
    """
    cache_key = (symbol, timeframe, lookahead_n)
    now = time.time()
    if cache_key in _CHART_CACHE:
        fetched_at, cached_df = _CHART_CACHE[cache_key]
        if now - fetched_at < _CHART_CACHE_TTL_SEC and cached_df is not None:
            print(f"[CHART_DATA] Cache hit for {symbol} ({timeframe})")
            return cached_df
        if now - fetched_at >= _CHART_CACHE_TTL_SEC:
            del _CHART_CACHE[cache_key]

    period_days, max_results = get_period_for_timeframe(timeframe, lookahead_n)
    period_days_int = int(period_days.replace("d", ""))

    # yfinance (단일 소스)
    yahoo_symbol = get_yahoo_symbol(symbol)
    last_key = yahoo_symbol
    if last_key in _LAST_REQUEST_TIME:
        elapsed = now - _LAST_REQUEST_TIME[last_key]
        if elapsed < _MIN_REQUEST_INTERVAL_SEC:
            await asyncio.sleep(_MIN_REQUEST_INTERVAL_SEC - elapsed)

    last_error = None
    for attempt in range(max_retries):
        try:
            _LAST_REQUEST_TIME[last_key] = time.time()
            df = await asyncio.to_thread(_fetch_chart_data_sync, symbol, timeframe, lookahead_n)
            if df is not None and not df.empty:
                _CHART_CACHE[cache_key] = (time.time(), df)
                print(f"[CHART_DATA] yfinance {len(df)} points for {symbol} ({timeframe})")
                return df
            last_error = ValueError("Empty or no data")
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "too many" in err_str or "429" in err_str or "rate" in err_str:
                wait = 3.0 * (attempt + 1)
                print(f"[CHART_DATA] Rate limit (attempt {attempt + 1}/{max_retries}), waiting {wait:.0f}s")
                await asyncio.sleep(wait)
            else:
                print(f"[CHART_DATA] Error for {symbol}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0 * (attempt + 1))

    print(f"[CHART_DATA] Failed after {max_retries} attempts for {symbol} ({timeframe}): {last_error}")
    return None

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    차트 데이터에 기술적 지표를 추가합니다.
    """
    if df.empty:
        return df

    # 계산을 위해 오름차순(과거->최신)으로 정렬
    df_calc = df.sort_values('Datetime', ascending=True).copy()

    # 1. 이동평균선 (EMA)
    df_calc['EMA5'] = df_calc['Close'].ewm(span=5, adjust=False).mean()
    df_calc['EMA10'] = df_calc['Close'].ewm(span=10, adjust=False).mean()
    df_calc['EMA20'] = df_calc['Close'].ewm(span=20, adjust=False).mean()
    df_calc['EMA50'] = df_calc['Close'].ewm(span=50, adjust=False).mean()
    df_calc['EMA200'] = df_calc['Close'].ewm(span=200, adjust=False).mean()

    # 2. RSI (Relative Strength Index)
    delta = df_calc['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df_calc['RSI'] = 100 - (100 / (1 + rs))

    # 3. MACD (Moving Average Convergence Divergence)
    exp1 = df_calc['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df_calc['Close'].ewm(span=26, adjust=False).mean()
    df_calc['MACD'] = exp1 - exp2
    df_calc['MACD_Signal'] = df_calc['MACD'].ewm(span=9, adjust=False).mean()
    df_calc['MACD_Hist'] = df_calc['MACD'] - df_calc['MACD_Signal']

    # 4. Bollinger Bands
    df_calc['BB_Mid'] = df_calc['Close'].rolling(window=20).mean()
    df_calc['BB_Std'] = df_calc['Close'].rolling(window=20).std()
    df_calc['BB_Upper'] = df_calc['BB_Mid'] + (df_calc['BB_Std'] * 2)
    df_calc['BB_Lower'] = df_calc['BB_Mid'] - (df_calc['BB_Std'] * 2)

    # 5. ATR (Average True Range, 14)
    high_low = df_calc['High'] - df_calc['Low']
    high_close = (df_calc['High'] - df_calc['Close'].shift(1)).abs()
    low_close = (df_calc['Low'] - df_calc['Close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df_calc['ATR'] = tr.rolling(14).mean()

    # 다시 내림차순(최신->과거)으로 정렬
    return df_calc.sort_values('Datetime', ascending=False)

def format_chart_data_for_llm(df: pd.DataFrame, symbol: str, timeframe: str) -> str:
    """
    차트 데이터와 기술적 지표를 LLM이 분석하기 쉬운 텍스트 형식으로 변환합니다.
    """
    if df is None or df.empty:
        return f"No chart data available for {symbol} ({timeframe})"
    
    # 기술적 지표 계산
    df_with_indicators = calculate_indicators(df)
    
    # 최신 50개 데이터 포인트만 사용
    df_recent = df_with_indicators.head(50)
    
    latest = df_recent.iloc[0]
    
    # 데이터 포맷팅
    lines = [
        f"=== {symbol} ({timeframe}) 애널리스트·단기트레이딩 기술 분석 데이터 ===",
        f"최신 가격: {latest['Close']:.2f}",
        f"최근 추세 분석:",
        f"- EMA5/10/20: {latest['EMA5']:.2f} / {latest['EMA10']:.2f} / {latest['EMA20']:.2f}",
        f"- EMA50/200: {latest['EMA50']:.2f} / {latest['EMA200']:.2f}",
        f"- RSI(14): {latest['RSI']:.2f} ({'과매수' if latest['RSI'] > 70 else '과매도' if latest['RSI'] < 30 else '중립'})",
        f"- MACD: {latest['MACD']:.2f} (Signal: {latest['MACD_Signal']:.2f}, Hist: {latest['MACD_Hist']:.2f})",
        f"- 볼린저 밴드: 상단 {latest['BB_Upper']:.2f}, 중단 {latest['BB_Mid']:.2f}, 하단 {latest['BB_Lower']:.2f}",
        "",
        "최근 30개 캔들 데이터 (기술 지표 포함):",
        "시간 | 시가 | 고가 | 저가 | 종가 | RSI | MACD_Hist | 거래량"
    ]
    
    for idx, row in df_recent.head(30).iterrows():
        dt = row['Datetime']
        dt_str = dt.strftime('%Y-%m-%d %H:%M') if hasattr(dt, 'strftime') else str(dt)
        rsi_val = f"{row['RSI']:.1f}" if not pd.isna(row['RSI']) else "N/A"
        macd_val = f"{row['MACD_Hist']:.2f}" if not pd.isna(row['MACD_Hist']) else "N/A"
        lines.append(
            f"{dt_str} | {row['Open']:.2f} | {row['High']:.2f} | {row['Low']:.2f} | {row['Close']:.2f} | "
            f"{rsi_val} | {macd_val} | {row['Volume']:.0f}"
        )
    
    return "\n".join(lines)
