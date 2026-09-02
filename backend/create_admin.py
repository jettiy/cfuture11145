"""
관리자 계정 생성/등록 스크립트
- 아이디: aaaa / 비밀번호: 1234 / 역할: ADMIN
- 이미 있으면 비밀번호 갱신 + ADMIN 권한 부여
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models import User, UserRole
from app.auth import get_password_hash

ADMIN_USERNAME = "aaaa"
ADMIN_PASSWORD = "1234"
ADMIN_NICKNAME = "관리자"


def ensure_admin():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == ADMIN_USERNAME).first()

        if user:
            # 기존 사용자: 비밀번호 갱신 + ADMIN 부여
            user.password_hash = get_password_hash(ADMIN_PASSWORD)
            user.role = UserRole.ADMIN
            db.commit()
            db.refresh(user)
            print(f"[OK] 기존 사용자 '{ADMIN_USERNAME}' 비밀번호 갱신 및 관리자 권한 부여 완료.")
            return True

        # 새 관리자 생성
        user = User(
            username=ADMIN_USERNAME,
            password_hash=get_password_hash(ADMIN_PASSWORD),
            nickname=ADMIN_NICKNAME,
            role=UserRole.ADMIN,
            pro_request_status="none",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[OK] 관리자 계정 생성 완료: {ADMIN_USERNAME} / **** (역할: {user.role.value})")
        return True

    except Exception as e:
        db.rollback()
        print(f"[ERROR] 오류: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("관리자 계정 등록: aaaa / 1234")
    print("-" * 50)
    ok = ensure_admin()
    print("-" * 50)
    if not ok:
        sys.exit(1)
    print("로그인: 아이디 aaaa, 비밀번호 1234")
