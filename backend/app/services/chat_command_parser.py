# -*- coding: utf-8 -*-
"""
채팅창 @종목명 키워드 한글 인식 로직.
- 유저 입력: @엔비디아 주가, @애플 실적, @테슬라 뉴스 등
- 매핑: 주가/가격/얼마 -> quote, 실적/어닝/매출 -> earnings, 뉴스/소식 -> news
"""
from typing import Optional, Dict, Any

# 한글/일반 종목명 -> FMP 티커 (우선 사용, 없으면 FMP search-name API로 조회)
KOREAN_NAME_TO_TICKER = {
    "엔비디아": "NVDA",
    "엔비디아주식": "NVDA",
    "nvidia": "NVDA",
    "애플": "AAPL",
    "애플주식": "AAPL",
    "apple": "AAPL",
    "테슬라": "TSLA",
    "테슬라주식": "TSLA",
    "tesla": "TSLA",
    "마이크로소프트": "MSFT",
    "마이크로소프트주식": "MSFT",
    "microsoft": "MSFT",
    "ms": "MSFT",
    "구글": "GOOGL",
    "알파벳": "GOOGL",
    "google": "GOOGL",
    "아마존": "AMZN",
    "아마존주식": "AMZN",
    "amazon": "AMZN",
    "메타": "META",
    "페이스북": "META",
    "meta": "META",
    "삼성전자": "005930.KS",
    "삼성": "005930.KS",
    "네이버": "035420.KS",
    "카카오": "035720.KS",
    "현대차": "005380.KS",
    "기아": "000270.KS",
    "SK하이닉스": "000660.KS",
    "하이닉스": "000660.KS",
}

# 키워드 -> FMP 명령 타입 (quote / earnings / news)
KEYWORDS_QUOTE = ["주가", "가격", "얼마", "현재가", "시세"]
KEYWORDS_EARNINGS = ["실적", "어닝", "매출", "분기실적", "실적발표"]
KEYWORDS_NEWS = ["뉴스", "소식", "기사", "최신뉴스"]


def _normalize_name(s: str) -> str:
    """종목명 후보 정규화 (공백 제거, 소문자화 for 영문)."""
    if not s:
        return ""
    t = s.strip()
    if t.isascii():
        return t.lower()
    return t


def _classify_keyword(rest: str) -> Optional[str]:
    """나머지 문장에서 키워드 감지 -> quote | earnings | news | None."""
    if not rest:
        return None
    r = rest.strip()
    for k in KEYWORDS_QUOTE:
        if k in r:
            return "quote"
    for k in KEYWORDS_EARNINGS:
        if k in r:
            return "earnings"
    for k in KEYWORDS_NEWS:
        if k in r:
            return "news"
    return None


def parse_stock_command(content: str) -> Optional[Dict[str, Any]]:
    """
    채팅 메시지에서 @종목명 키워드 패턴 파싱.
    - content 예: "@엔비디아 주가", "@애플 실적", "@테슬라 뉴스"
    - 반환: {"name": "엔비디아", "command_type": "quote", "user_question": "주가"} 또는 None
    """
    if not content or not isinstance(content, str):
        return None
    stripped = content.strip()
    if not stripped.startswith("@"):
        return None
    # @ 제거 후 첫 토큰 = 종목명 후보, 나머지 = 키워드/질문
    after_at = stripped[1:].strip()
    if not after_at:
        return None
    parts = after_at.split(maxsplit=1)
    name_candidate = _normalize_name(parts[0])
    rest = parts[1].strip() if len(parts) > 1 else ""
    command_type = _classify_keyword(rest)
    if not command_type:
        return None
    return {
        "name": name_candidate if not name_candidate.isascii() else parts[0].strip(),
        "name_normalized": name_candidate,
        "command_type": command_type,
        "user_question": rest or "",
    }


def resolve_ticker_from_map(name_normalized: str) -> Optional[str]:
    """정적 매핑에서만 티커 반환. 한글은 그대로, 영문은 소문자로 매칭."""
    if not name_normalized:
        return None
    return KOREAN_NAME_TO_TICKER.get(name_normalized) or KOREAN_NAME_TO_TICKER.get(
        name_normalized.lower() if name_normalized.isascii() else name_normalized
    )
