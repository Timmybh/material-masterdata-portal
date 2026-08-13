-- Material Masterdata Portal V1.5.1 migration
ALTER TABLE material_requests
    ADD COLUMN IF NOT EXISTS supplier_material_code VARCHAR(150);

CREATE TABLE IF NOT EXISTS sync_status (
    source_name VARCHAR(100) PRIMARY KEY,
    last_synced_at TIMESTAMPTZ,
    row_count BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'SUCCESS',
    message TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO sync_status(source_name,last_synced_at,row_count,status,message,updated_at)
VALUES('BRAVO', NOW(), (SELECT COUNT(*) FROM materials), 'SUCCESS', 'Danh mục vật tư hiện tại trong PostgreSQL', NOW())
ON CONFLICT(source_name) DO UPDATE SET
    row_count = EXCLUDED.row_count,
    updated_at = NOW();

CREATE TABLE IF NOT EXISTS email_logs (
    id BIGSERIAL PRIMARY KEY,
    request_id BIGINT REFERENCES material_requests(id) ON DELETE SET NULL,
    recipient VARCHAR(255) NOT NULL,
    subject VARCHAR(500) NOT NULL,
    email_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_logs_request_id ON email_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_email_logs_created_at ON email_logs(created_at DESC);
