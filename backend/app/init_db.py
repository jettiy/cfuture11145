"""
초기 데이터베이스 설정 스크립트
채널 생성 등
"""
from app.database import SessionLocal, engine, Base
from app.migrations import run_sqlite_migrations
from app.models import Channel, User, UserRole

def init_db():
    Base.metadata.create_all(bind=engine)
    run_sqlite_migrations(engine)
    db = SessionLocal()
    
    try:
        # 기본 채널 생성
        channels = [
            {"name": "Global", "symbol": None},
            {"name": "NASDAQ", "symbol": "NASDAQ"},
            {"name": "HSI", "symbol": "HSI"},
            {"name": "GOLD", "symbol": "GOLD"},
            {"name": "OIL", "symbol": "OIL"}
        ]
        
        for ch_data in channels:
            existing = db.query(Channel).filter(Channel.name == ch_data["name"]).first()
            if not existing:
                channel = Channel(**ch_data)
                db.add(channel)
        
        # 관리자 계정은 create_admin.py로 별도 생성
        
        db.commit()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
