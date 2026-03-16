from __future__ import annotations

import re
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.engine import Engine


def _has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
    cols = {r[1] for r in rows}
    return column_name in cols


def _get_column_notnull(engine: Engine, table_name: str, column_name: str) -> bool | None:
    """컬럼의 NOT NULL 제약 조건 여부를 반환"""
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
        for row in rows:
            if row[1] == column_name:
                return bool(row[3])  # notnull (3번째 인덱스)
    return None


def _get_column_default(engine: Engine, table_name: str, column_name: str) -> str | None:
    """컬럼의 기본값을 반환"""
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
        for row in rows:
            if row[1] == column_name:
                return row[4]  # dflt_value (4번째 인덱스)
    return None


def _migrate_users_table_nullable(engine: Engine) -> None:
    """
    users 테이블의 name, phone, email 컬럼을 nullable로 변경.
    SQLite는 NOT NULL 제약을 직접 제거할 수 없으므로 테이블을 재생성해야 함.
    """
    with engine.connect() as conn:
        # 기존 테이블이 있는지 확인
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        ).fetchone()
        if not result:
            return  # 테이블이 없으면 스킵 (create_all에서 생성될 것)
        
        # name, phone, email이 NOT NULL인지 확인
        name_notnull = _get_column_notnull(engine, "users", "name")
        phone_notnull = _get_column_notnull(engine, "users", "phone")
        email_notnull = _get_column_notnull(engine, "users", "email")
        created_at_default = _get_column_default(engine, "users", "created_at")
        
        # 모두 nullable이고 created_at에 기본값이 있으면 마이그레이션 불필요
        if not name_notnull and not phone_notnull and not email_notnull and created_at_default:
            return
        
        print("[MIGRATION] Migrating users table: making name/phone/email nullable...")
        
        # 1. 기존 데이터 백업
        # 컬럼 이름을 PRAGMA로 가져오기
        col_info = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        column_names = [row[1] for row in col_info]  # row[1]은 컬럼 이름
        
        backup_data = conn.execute(text("SELECT * FROM users")).fetchall()
        
        with engine.begin() as trans_conn:
            # 2. 임시 테이블 생성 (새 스키마)
            trans_conn.execute(text("""
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(100),
                    phone VARCHAR(20),
                    email VARCHAR(100),
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    nickname VARCHAR(50) NOT NULL UNIQUE,
                    role VARCHAR(20) NOT NULL,
                    pro_request_status VARCHAR(20) NOT NULL DEFAULT 'none',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME
                )
            """))
            
            # 3. 데이터 복원
            if backup_data and column_names:
                for row in backup_data:
                    # 딕셔너리로 변환
                    row_dict = dict(zip(column_names, row))
                    trans_conn.execute(
                        text("""
                            INSERT INTO users_new 
                            (id, name, phone, email, username, password_hash, nickname, role, pro_request_status, created_at, updated_at)
                            VALUES (:id, :name, :phone, :email, :username, :password_hash, :nickname, :role, :pro_request_status, :created_at, :updated_at)
                        """),
                        {
                            "id": row_dict.get("id"),
                            "name": row_dict.get("name"),
                            "phone": row_dict.get("phone"),
                            "email": row_dict.get("email"),
                            "username": row_dict.get("username"),
                            "password_hash": row_dict.get("password_hash"),
                            "nickname": row_dict.get("nickname"),
                            "role": row_dict.get("role"),
                            "pro_request_status": row_dict.get("pro_request_status", "none"),
                            "created_at": row_dict.get("created_at"),
                            "updated_at": row_dict.get("updated_at")
                        }
                    )
            
            # 4. 기존 테이블 삭제 및 새 테이블 이름 변경
            trans_conn.execute(text("DROP TABLE users"))
            trans_conn.execute(text("ALTER TABLE users_new RENAME TO users"))
            
            # 5. 인덱스 재생성
            trans_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_username ON users(username)"))
            trans_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_phone ON users(phone)"))
            trans_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)"))
        
        print("[MIGRATION] users table migration completed successfully")


def run_postgres_rls(engine: Engine) -> None:
    """PostgreSQL(Supabase 포함) 사용 시 RLS 활성화 및 정책 적용. SQLite는 스킵."""
    if engine.dialect.name != "postgresql":
        return
    sql_path = Path(__file__).parent / "sql_rls_postgres.sql"
    if not sql_path.exists():
        return
    try:
        sql_content = sql_path.read_text(encoding="utf-8")
        # ";\n" 단위로 분리 후, ")" 만 있는 조각은 이전 문장에 붙임 (CREATE POLICY ... ); 처리)
        parts = re.split(r';\s*\n', sql_content)
        statements = []
        for p in parts:
            s = p.strip()
            if not s or s.startswith("--"):
                continue
            if re.match(r'^\)\s*$', s):
                if statements and not statements[-1].rstrip().endswith(";"):
                    statements[-1] = statements[-1].rstrip() + ");"
            else:
                statements.append(s if s.endswith(";") else s + ";")
        with engine.begin() as conn:
            for stmt in statements:
                if stmt.strip():
                    conn.execute(text(stmt))
        print("[MIGRATION] PostgreSQL RLS enabled successfully")
    except Exception as e:
        print(f"[MIGRATION] PostgreSQL RLS apply skipped or failed: {e}")
        import traceback
        traceback.print_exc()


def run_sqlite_migrations(engine: Engine) -> None:
    """
    매우 간단한(가벼운) SQLite 마이그레이션.
    - 기존 DB 파일이 있을 때, 모델에 새로 추가된 컬럼이 없으면 ALTER TABLE로 추가한다.
    - Alembic 도입 전까지 임시/실용적인 방식으로 운영.
    """
    # users 테이블의 name/phone/email을 nullable로 변경
    try:
        _migrate_users_table_nullable(engine)
    except Exception as e:
        print(f"[MIGRATION] Error migrating users table: {e}")
        import traceback
        traceback.print_exc()
    
    # users.pro_request_status
    try:
        if _has_column(engine, "users", "pro_request_status") is False:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN pro_request_status VARCHAR(20) NOT NULL DEFAULT 'none'"
                    )
                )
            print("[MIGRATION] Added users.pro_request_status")
    except Exception as e:
        # users 테이블 자체가 없을 수 있음(최초 실행). create_all에서 생성될 것.
        print(f"[MIGRATION] Skipped users.pro_request_status: {e}")

    # support_chats.request_type
    try:
        if _has_column(engine, "support_chats", "request_type") is False:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE support_chats "
                        "ADD COLUMN request_type VARCHAR(20) NOT NULL DEFAULT 'pro_upgrade'"
                    )
                )
            print("[MIGRATION] Added support_chats.request_type")
    except Exception as e:
        print(f"[MIGRATION] Skipped support_chats.request_type: {e}")
    
    # economic_indicators.ko_name
    try:
        if _has_column(engine, "economic_indicators", "ko_name") is False:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE economic_indicators ADD COLUMN ko_name VARCHAR(200)")
                )
            print("[MIGRATION] Added economic_indicators.ko_name")
    except Exception as e:
        print(f"[MIGRATION] Skipped economic_indicators.ko_name: {e}")
    
    # earnings.ko_company_name
    try:
        if _has_column(engine, "earnings", "ko_company_name") is False:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE earnings ADD COLUMN ko_company_name VARCHAR(200)")
                )
            print("[MIGRATION] Added earnings.ko_company_name")
    except Exception as e:
        print(f"[MIGRATION] Skipped earnings.ko_company_name: {e}")
    
    # economic_calendar.ko_event_name
    try:
        if _has_column(engine, "economic_calendar", "ko_event_name") is False:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE economic_calendar ADD COLUMN ko_event_name VARCHAR(300)")
                )
            print("[MIGRATION] Added economic_calendar.ko_event_name")
    except Exception as e:
        print(f"[MIGRATION] Skipped economic_calendar.ko_event_name: {e}")
    
    # signals.llm_cost
    try:
        if _has_column(engine, "signals", "llm_cost") is False:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE signals ADD COLUMN llm_cost FLOAT")
                )
            print("[MIGRATION] Added signals.llm_cost")
    except Exception as e:
        print(f"[MIGRATION] Skipped signals.llm_cost: {e}")

    # earnings.market_reaction_percent
    try:
        if _has_column(engine, "earnings", "market_reaction_percent") is False:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE earnings ADD COLUMN market_reaction_percent FLOAT")
                )
            print("[MIGRATION] Added earnings.market_reaction_percent")
    except Exception as e:
        print(f"[MIGRATION] Skipped earnings.market_reaction_percent: {e}")

    # economic_calendar.link
    try:
        if _has_column(engine, "economic_calendar", "link") is False:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE economic_calendar ADD COLUMN link VARCHAR(1000)")
                )
            print("[MIGRATION] Added economic_calendar.link")
    except Exception as e:
        print(f"[MIGRATION] Skipped economic_calendar.link: {e}")

    # economic_indicators.link & is_released
    try:
        if _has_column(engine, "economic_indicators", "link") is False:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE economic_indicators ADD COLUMN link VARCHAR(1000)")
                )
            print("[MIGRATION] Added economic_indicators.link")
        if _has_column(engine, "economic_indicators", "is_released") is False:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE economic_indicators ADD COLUMN is_released BOOLEAN DEFAULT 0")
                )
            print("[MIGRATION] Added economic_indicators.is_released")
    except Exception as e:
        print(f"[MIGRATION] Skipped economic_indicators updates: {e}")
