CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'USER',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS materials (
    id BIGSERIAL PRIMARY KEY,
    material_code VARCHAR(100) UNIQUE NOT NULL,
    material_name VARCHAR(500) NOT NULL,
    description TEXT,
    unit VARCHAR(50),
    material_group VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_materials_search
ON materials USING GIN (
    to_tsvector('simple', coalesce(material_code,'') || ' ' || coalesce(material_name,'') || ' ' || coalesce(description,''))
);

CREATE TABLE IF NOT EXISTS material_requests (
    id BIGSERIAL PRIMARY KEY,
    request_no VARCHAR(50) UNIQUE NOT NULL,
    requester_id BIGINT REFERENCES users(id),
    proposed_name VARCHAR(500) NOT NULL,
    description TEXT,
    unit VARCHAR(50),
    material_group VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING_MASTERDATA',
    masterdata_note TEXT,
    accounting_note TEXT,
    result_material_code VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS request_history (
    id BIGSERIAL PRIMARY KEY,
    request_id BIGINT NOT NULL REFERENCES material_requests(id) ON DELETE CASCADE,
    actor_id BIGINT REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    from_status VARCHAR(50),
    to_status VARCHAR(50),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO users (email, full_name, role) VALUES
('user@example.com', 'Người dùng Demo', 'USER'),
('masterdata@example.com', 'Nhân sự phụ trách Masterdata', 'MASTERDATA'),
('accounting@example.com', 'Kế toán Demo', 'ACCOUNTING')
ON CONFLICT (email) DO NOTHING;

INSERT INTO materials (material_code, material_name, description, unit, material_group) VALUES
('VT000001', 'Vật tư mẫu 01', 'Dữ liệu mẫu phục vụ tra cứu Full Text Search', 'PCS', 'GENERAL'),
('VT000002', 'Vật tư mẫu 02', 'Dữ liệu mẫu ban đầu của Material Masterdata Portal', 'PCS', 'GENERAL')
ON CONFLICT (material_code) DO NOTHING;
