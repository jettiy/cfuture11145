-- PostgreSQL RLS (Row Level Security) 활성화
-- Supabase 또는 PostgreSQL 사용 시 이 스크립트를 실행하세요.
-- 정책: 인증된 사용자는 자신의 데이터만 읽을 수 있음 (app.current_user_id, app.is_admin 세션 변수 사용)

-- 세션 변수 (앱에서 요청 시 설정):
--   SET LOCAL app.current_user_id = <user_id>;
--   SET LOCAL app.is_admin = true|false;

-- users: 본인 행만 읽기/수정, admin은 전체
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_select_own_or_admin" ON users;
CREATE POLICY "users_select_own_or_admin" ON users FOR SELECT
  USING (
    (current_setting('app.current_user_id', true) IS NOT NULL AND id = current_setting('app.current_user_id', true)::int)
    OR (current_setting('app.is_admin', true) = 'true')
  );

DROP POLICY IF EXISTS "users_update_own_or_admin" ON users;

-- messages: 본인 메시지 또는 봇 메시지(user_id NULL) 또는 admin
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "messages_select_own_or_admin" ON messages FOR SELECT
  USING (
    (current_setting('app.current_user_id', true) IS NOT NULL AND (user_id = current_setting('app.current_user_id', true)::int OR user_id IS NULL))
    OR (current_setting('app.is_admin', true) = 'true')
  );

DROP POLICY IF EXISTS "messages_insert_own_or_admin" ON messages FOR INSERT
  WITH CHECK (
    (current_setting('app.current_user_id', true) IS NOT NULL AND user_id = current_setting('app.current_user_id', true)::int)
    OR (current_setting('app.is_admin', true) = 'true')
  );

-- signals: 본인 시그널만 읽기, admin은 전체
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "signals_select_own_or_admin" ON signals FOR SELECT
  USING (
    (current_setting('app.current_user_id', true) IS NOT NULL AND user_id = current_setting('app.current_user_id', true)::int)
    OR (current_setting('app.is_admin', true) = 'true')
  );

DROP POLICY IF EXISTS "signals_insert_own" ON signals FOR INSERT
  WITH CHECK (
    current_setting('app.current_user_id', true) IS NOT NULL AND user_id = current_setting('app.current_user_id', true)::int
  );

-- support_chats: 본인(user_id 또는 admin_id) 또는 admin
ALTER TABLE support_chats ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "support_chats_select_own_or_admin" ON support_chats FOR SELECT
  USING (
    (current_setting('app.current_user_id', true) IS NOT NULL AND (user_id = current_setting('app.current_user_id', true)::int OR admin_id = current_setting('app.current_user_id', true)::int))
    OR (current_setting('app.is_admin', true) = 'true')
  );

-- support_messages: 본인 또는 admin (support_chat 소유자/담당자 확인은 앱 레이어에서)
ALTER TABLE support_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "support_messages_select_own_or_admin" ON support_messages FOR SELECT
  USING (
    (current_setting('app.current_user_id', true) IS NOT NULL AND user_id = current_setting('app.current_user_id', true)::int)
    OR (current_setting('app.is_admin', true) = 'true')
  );
