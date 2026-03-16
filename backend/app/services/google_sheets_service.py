import os
import logging
from typing import Optional

# 구글 시트 연동을 위한 라이브러리 (필요 시 pip install gspread oauth2client)
# 실제 운영 환경에서는 서비스 계정 키 파일(.json)과 시트 ID가 필요합니다.

logger = logging.getLogger(__name__)

async def sync_user_to_sheet(name: Optional[str], phone: Optional[str], email: Optional[str], role: str):
    """
    PRO 가입 신청자 또는 승인된 유저 정보를 구글 스프레드시트에 동기화합니다.
    """
    try:
        # TODO: 실제 gspread 연동 로직
        # 1. 인증 정보 로드 (os.getenv("GOOGLE_SHEETS_CREDENTIALS"))
        # 2. 시트 오픈 (os.getenv("GOOGLE_SHEETS_ID"))
        # 3. 데이터 추가/업데이트
        
        # 데모용 로그 출력
        log_msg = f"[GOOGLE_SHEET_SYNC] Name: {name}, Phone: {phone}, Email: {email}, Role: {role}"
        print(log_msg)
        logger.info(log_msg)
        
        # 파일로도 시뮬레이션 저장
        with open("pro_users_sheet_mock.csv", "a", encoding="utf-8") as f:
            f.write(f"{name},{phone},{email},{role}\n")
            
        return True
    except Exception as e:
        logger.error(f"Failed to sync to Google Sheets: {e}")
        return False
