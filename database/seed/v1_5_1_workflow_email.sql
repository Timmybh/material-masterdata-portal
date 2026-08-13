-- Material Masterdata Portal V1.5.1 migration
-- Compatible with sync_status created by the Excel Bravo import script.

ALTER TABLE material_requests
    ADD COLUMN IF NOT EXISTS supplier_material_code VARCHAR(150);

CREATE TABLE IF NOT EXISTS sync_status (
    source_name VARCHAR(100) PRIMARY KEY,
    last_sync_at TIMESTAMPTZ,
    row_count BIGINT NOT NULL DEFAULT 0,
    note TEXT
);

-- V1.5.1 canonical columns. ALTER is required because CREATE TABLE IF NOT EXISTS
-- does not add missing columns when sync_status already exists.
ALTER TABLE sync_status ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;
ALTER TABLE sync_status ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'SUCCESS';
ALTER TABLE sync_status ADD COLUMN IF NOT EXISTS message TEXT;
ALTER TABLE sync_status ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Preserve values written by the previous Excel import script.
UPDATE sync_status
SET last_synced_at = COALESCE(last_synced_at, last_sync_at),
    message = COALESCE(message, note),
    updated_at = NOW()
WHERE source_name = 'BRAVO';

INSERT INTO sync_status(
    source_name, last_sync_at, last_synced_at, row_count,
    status, note, message, updated_at
)
VALUES(
    'BRAVO',
    NOW(),
    NOW(),
    (SELECT COUNT(*) FROM materials),
    'SUCCESS',
    'Danh mục vật tư hiện tại trong PostgreSQL',
    'Danh mục vật tư hiện tại trong PostgreSQL',
    NOW()
)
ON CONFLICT(source_name) DO UPDATE SET
    last_synced_at = COALESCE(sync_status.last_synced_at, sync_status.last_sync_at, EXCLUDED.last_synced_at),
    row_count = EXCLUDED.row_count,
    status = 'SUCCESS',
    message = COALESCE(sync_status.message, sync_status.note, EXCLUDED.message),
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
