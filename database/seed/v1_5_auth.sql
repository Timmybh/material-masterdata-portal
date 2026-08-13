-- Material Masterdata Portal V1.5 authentication migration + demo accounts
-- Safe to run repeatedly.

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

INSERT INTO users (email, full_name, role, is_active, password_hash) VALUES
('admin@dovitec.local', 'Quản trị hệ thống', 'ADMIN', TRUE, 'pbkdf2_sha256$200000$adminsalt$94rnujyys9gbX/0gu6Z/bwcg3CUScJ7ReRxfzec9Jlc=')
ON CONFLICT (email) DO UPDATE SET
  full_name = EXCLUDED.full_name,
  role = EXCLUDED.role,
  is_active = EXCLUDED.is_active,
  password_hash = EXCLUDED.password_hash,
  updated_at = NOW();

UPDATE users SET password_hash='pbkdf2_sha256$200000$usersalt$Wi2y/s8h3Hk9dKwg+1rbNrerPE4Wvt8OTsbETLdQk6I=', updated_at=NOW() WHERE email='user@example.com';
UPDATE users SET password_hash='pbkdf2_sha256$200000$user2salt$UVHQJ3+fEq897hamFwP3qBJsc8qu9KN4J8K1Z0cUVC4=', updated_at=NOW() WHERE email='user2@example.com';
UPDATE users SET password_hash='pbkdf2_sha256$200000$mastersalt$LJ756cYj9Yc7mL+W8mvJ2mWLWibLoM0h7ClKFHn2tIs=', updated_at=NOW() WHERE email='masterdata@example.com';
UPDATE users SET password_hash='pbkdf2_sha256$200000$acctsalt$lwubiU380p5tE+1YNZy0klAHfB+/49Y7tfDVtPhjfps=', updated_at=NOW() WHERE email='accounting@example.com';
