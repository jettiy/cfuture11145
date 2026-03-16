"""
인베스팅닷컴(https://kr.investing.com/earnings-calendar) 실적 캘린더 수집
매일 08:00 KST에 오늘의 실적 갱신용.
"""
import re
import httpx
from httpx import DecodingError
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Earnings

BASE_URL = "https://kr.investing.com/earnings-calendar/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _parse_number_cell(text: str) -> float | None:
    """'--', '2,495.33B', '23.58T' 등 파싱. B=10억, T=1조, M=100만."""
    if not text or text.strip() in ("--", "", "N/A"):
        return None
    text = text.strip().replace(",", "").replace(" ", "")
    mult = 1.0
    if text.endswith("B"):
        text = text[:-1]
        mult = 1e9
    elif text.endswith("T"):
        text = text[:-1]
        mult = 1e12
    elif text.endswith("M"):
        text = text[:-1]
        mult = 1e6
    try:
        return float(text) * mult
    except ValueError:
        return None


async def fetch_investing_earnings_today() -> int:
    """
    인베스팅닷컴에서 오늘(KST) 실적 캘린더를 가져와 DB에 저장.
    기존 '오늘' 실적 레코드는 삭제 후 새로 채움.
    반환: 저장된 레코드 수.
    """
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).date()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=kst).astimezone(timezone.utc)
    today_end = today_start + timedelta(days=1)

    db = SessionLocal()
    try:
        # 오늘 날짜 실적만 삭제 (08:00 갱신 시 기존 오늘 데이터 제거)
        deleted = db.query(Earnings).filter(
            Earnings.earnings_date >= today_start,
            Earnings.earnings_date < today_end,
        ).delete()
        db.commit()
        if deleted:
            print(f"[INVESTING] Cleared {deleted} existing today earnings for refresh")

        rows: list[dict] = []
        # Brotli 응답 시 Windows/일부 환경에서 DecodingError 발생 가능 → gzip/deflate만 허용
        req_headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        }
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            try:
                resp = await client.get(BASE_URL, headers=req_headers)
            except DecodingError as e:
                print(f"[INVESTING] DecodingError (brotli 등): {e}")
                return 0
            if resp.status_code != 200:
                print(f"[INVESTING] HTTP {resp.status_code}")
                return 0

        soup = BeautifulSoup(resp.text, "html.parser")

        # 테이블: investing.com은 보통 #earningsCalendarData 또는 class로 테이블 감싸짐
        # 더 정확한 선택자를 사용하여 테이블 찾기
        table = soup.find("table", id="earningsCalendarData")
        if not table:
            # 다른 가능한 테이블 ID나 클래스 시도
            table = soup.find("table", {"id": re.compile(r"earnings|calendar", re.I)})
        if not table:
            table = soup.find("table", class_=re.compile(r"earnings|calendar", re.I))
        if not table:
            # 모든 테이블 중 가장 큰 것 선택 (보통 실적 캘린더가 가장 큼)
            all_tables = soup.find_all("table")
            if all_tables:
                table = max(all_tables, key=lambda t: len(t.find_all("tr")))
        if not table:
            print("[INVESTING] No table found in page")
            print(f"[INVESTING] Page content preview: {resp.text[:500]}")
            return 0

        thead = table.find("thead")
        tbody = table.find("tbody") or table
        trs = (tbody or table).find_all("tr") if tbody else table.find_all("tr")
        if thead:
            header_tr = thead.find("tr")
            if header_tr:
                trs = [t for t in trs if t != header_tr]

        # 오늘 날짜 문자열 (한국어 페이지: "2025년 8월 11일 월요일" 또는 "YYYY년 M월 D일")
        today_str_kr = f"{today.year}년 {today.month}월 {today.day}일"
        current_date_cell = None

        for tr in trs:
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue

            # 날짜 행: 한 셀에 "2025년 8월 11일 월요일" 형태
            first_text = (cells[0].get_text() or "").strip()
            if today_str_kr in first_text and len(cells) <= 2:
                current_date_cell = first_text
                continue

            # 데이터 행: 회사 | 주당순이익 | / 예측 | 매출 | / 예측 | 총 시가 | 시간
            if len(cells) < 5:
                continue

            # 회사 셀: "HMM (011200)" 또는 링크 내 텍스트
            company_cell = cells[0]
            company_link = company_cell.find("a", href=True)
            symbol = ""
            company_name = (company_cell.get_text() or "").strip()
            if company_link:
                href = company_link.get("href", "")
                # /equities/hyundai-merchant-marine-earnings -> symbol은 보통 코드 (한국주식 6자리 등)
                match = re.search(r"equities/([^/-]+)", href)
                if match:
                    symbol = match.group(1).upper()[:20]
                # 괄호 안 코드 추출 (한국: 011200)
                code_match = re.search(r"\((\d+)\)", company_name)
                if code_match:
                    symbol = symbol or code_match.group(1)
            if not symbol and company_name:
                symbol = re.sub(r"\s+", "", company_name)[:20] or "N/A"

            # 주당순이익 실제 / 예측 (보통 2, 3번째 셀)
            eps_actual = _parse_number_cell(cells[1].get_text() if len(cells) > 1 else "")
            eps_forecast = _parse_number_cell(cells[2].get_text() if len(cells) > 2 else "")
            # 매출 실제 / 예측
            rev_actual = _parse_number_cell(cells[3].get_text() if len(cells) > 3 else "")
            rev_forecast = _parse_number_cell(cells[4].get_text() if len(cells) > 4 else "")

            # 시간 셀 (있으면 파싱)
            time_str = (cells[6].get_text() if len(cells) > 6 else "").strip() or None
            earnings_dt = datetime.combine(today, datetime.min.time()).replace(tzinfo=kst)
            if time_str and re.match(r"\d{1,2}:\d{2}", time_str):
                try:
                    h, m = map(int, time_str.split(":")[:2])
                    earnings_dt = earnings_dt.replace(hour=h, minute=m, second=0, microsecond=0)
                except Exception:
                    pass
            earnings_dt_utc = earnings_dt.astimezone(timezone.utc)

            rows.append({
                "symbol": symbol or "N/A",
                "company_name": company_name or symbol,
                "ko_company_name": company_name if company_name and re.search(r"[가-힣]", company_name) else None,
                "quarter": None,
                "earnings_date": earnings_dt_utc,
                "eps_actual": eps_actual,
                "eps_forecast": eps_forecast,
                "revenue_actual": rev_actual,
                "revenue_forecast": rev_forecast,
                "source": "investing.com",
            })

        # 중복 제거 (symbol + date)
        seen = set()
        unique_rows = []
        for r in rows:
            key = (r["symbol"], r["earnings_date"].isoformat())
            if key in seen:
                continue
            seen.add(key)
            unique_rows.append(r)

        for r in unique_rows[:80]:  # 최대 80건
            e = Earnings(**r)
            db.add(e)
        db.commit()
        count = len(unique_rows[:80])
        print(f"[INVESTING] Saved {count} today earnings from kr.investing.com/earnings-calendar")
        return count

    except Exception as e:
        print(f"[INVESTING] Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 0
    finally:
        db.close()
