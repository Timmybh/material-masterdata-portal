from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_settings

settings = get_settings()
connect_args = {
    "connect_timeout": settings.db_connect_timeout_seconds,
    "application_name": "MaterialMasterdataPortal",
    "options": (
        f"-c statement_timeout={settings.db_statement_timeout_ms} "
        f"-c lock_timeout={settings.db_lock_timeout_ms}"
    ),
}
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
    pool_reset_on_return="rollback",
    pool_use_lifo=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        # Nâng cấp an toàn database V1.2/V1.4; lệnh có thể chạy lại nhiều lần.
        item_columns = {
            "new_code": "VARCHAR(100)", "old_code": "VARCHAR(100)", "parent_id": "INTEGER",
            "is_group": "BOOLEAN NOT NULL DEFAULT FALSE", "source_extra_1": "TEXT", "source_extra_2": "TEXT", "name2": "TEXT", "item_custom": "TEXT",
            "is_customs": "BOOLEAN NOT NULL DEFAULT FALSE", "is_item_with_color": "BOOLEAN NOT NULL DEFAULT FALSE",
            "is_item_with_size": "BOOLEAN NOT NULL DEFAULT FALSE", "is_item_with_art": "BOOLEAN NOT NULL DEFAULT FALSE",
            "is_item_with_product_cost_id": "BOOLEAN NOT NULL DEFAULT FALSE", "is_item_with_biz_doc_id_c2": "BOOLEAN NOT NULL DEFAULT FALSE",
            "is_item_with_symmetrical": "BOOLEAN NOT NULL DEFAULT FALSE", "is_item_with_color_product": "BOOLEAN NOT NULL DEFAULT FALSE",
            "product_cost_info": "TEXT", "product_item_code": "VARCHAR(100)", "branch_code": "VARCHAR(100)",
            "is_material": "BOOLEAN NOT NULL DEFAULT FALSE", "source_created_by": "INTEGER", "source_created_at": "TIMESTAMPTZ",
            "source_modified_by": "INTEGER", "source_select_key": "BOOLEAN", "extra_data": "TEXT"
        }
        request_columns = {
            "requester_name":"VARCHAR(255) NOT NULL DEFAULT ''", "department":"VARCHAR(255) NOT NULL DEFAULT ''",
            "item_type_name":"VARCHAR(100)", "parent_code":"VARCHAR(100)", "kind_code":"VARCHAR(100)", "brand":"VARCHAR(255)",
            "customer_code":"VARCHAR(100)", "branch_code":"VARCHAR(100)", "is_material":"BOOLEAN NOT NULL DEFAULT FALSE",
            "with_color":"BOOLEAN NOT NULL DEFAULT FALSE", "with_size":"BOOLEAN NOT NULL DEFAULT FALSE", "with_art":"BOOLEAN NOT NULL DEFAULT FALSE",
            "submitted_at":"TIMESTAMPTZ NOT NULL DEFAULT NOW()", "accounting_note":"TEXT", "code_issued_at":"TIMESTAMPTZ"
        }
        for name, sql_type in item_columns.items(): conn.execute(text(f"ALTER TABLE items ADD COLUMN IF NOT EXISTS {name} {sql_type}"))
        for name, sql_type in request_columns.items(): conn.execute(text(f"ALTER TABLE material_requests ADD COLUMN IF NOT EXISTS {name} {sql_type}"))
        conn.execute(text("UPDATE material_requests SET code_issued_at = updated_at WHERE status = 'COMPLETED' AND code_issued_at IS NULL"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_material_requests_code_issued_at ON material_requests(code_issued_at DESC)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(100)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username_lower ON users (LOWER(username)) WHERE username IS NOT NULL"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_email_lower ON users (LOWER(email))"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_items_code ON items(code)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_items_fts ON items USING GIN (to_tsvector('simple', search_text))"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_items_trgm ON items USING GIN (search_text gin_trgm_ops)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_items_code_trgm ON items USING GIN (code gin_trgm_ops)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_items_code_lower_trgm ON items USING GIN (LOWER(code) gin_trgm_ops)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_items_old_code_trgm ON items USING GIN (old_code gin_trgm_ops)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_items_new_code_trgm ON items USING GIN (new_code gin_trgm_ops)"))
        import_job_columns = {
            "job_id": "UUID", "source_path": "TEXT", "schedule_key": "VARCHAR(100)",
            "phase": "VARCHAR(30)", "queued_at": "TIMESTAMPTZ", "worker_id": "VARCHAR(255)",
            "processed": "INTEGER", "total_rows": "INTEGER", "duration_seconds": "NUMERIC(12,3)",
        }
        for name, sql_type in import_job_columns.items():
            conn.execute(text(f"ALTER TABLE import_run_history ADD COLUMN IF NOT EXISTS {name} {sql_type}"))
        conn.execute(text("UPDATE import_run_history SET queued_at = started_at WHERE queued_at IS NULL"))
        conn.execute(text("UPDATE import_run_history SET status = CASE status WHEN 'SUCCESS' THEN 'succeeded' WHEN 'FAILED' THEN 'failed' WHEN 'RUNNING' THEN 'failed' ELSE LOWER(status) END"))
        conn.execute(text("UPDATE import_run_history SET completed_at = COALESCE(completed_at, NOW()), error = COALESCE(error, 'Job import cũ bị gián đoạn trước khi nâng cấp') WHERE status = 'failed' AND completed_at IS NULL"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_import_run_history_job_id ON import_run_history(job_id) WHERE job_id IS NOT NULL"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_import_run_history_schedule_key ON import_run_history(schedule_key) WHERE schedule_key IS NOT NULL"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_import_run_history_one_active ON import_run_history ((1)) WHERE status IN ('queued', 'running')"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_import_run_history_queued_at ON import_run_history(queued_at DESC)"))
        expected=set(item_columns)|{"id","code","name","item_type_name","parent_code","item_group_code","kind_code","customer_code","unit_price","is_active","search_text","source_modified_at"}
        actual=set(conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='items'")).scalars())
        missing=expected-actual
        if missing:
            raise RuntimeError(f"Migration items chưa đầy đủ, thiếu cột: {', '.join(sorted(missing))}")
    from .models import AutoImportConfig, ImportRunHistory
    with SessionLocal() as db:
        config=db.get(AutoImportConfig,1)
        if not config:
            db.add(AutoImportConfig(
                id=1,
                enabled=settings.auto_import_enabled,
                file_path=settings.auto_import_file_path,
                hour=settings.auto_import_hour,
                minute=settings.auto_import_minute,
                timezone=settings.auto_import_timezone,
            ))
            db.commit()
        elif config.last_started_at and not db.scalar(select(func.count(ImportRunHistory.id))):
            db.add(ImportRunHistory(
                trigger=config.last_trigger or "AUTO",
                source_name=config.file_path if config.last_trigger == "AUTO" else "Lần import trước khi nâng cấp",
                status={"SUCCESS":"succeeded","FAILED":"failed","RUNNING":"failed"}.get(config.last_status or "", "failed"),
                queued_at=config.last_started_at,
                started_at=config.last_started_at,
                completed_at=config.last_completed_at,
                imported=config.last_imported,
                skipped=config.last_skipped,
                error=config.last_error,
            ))
            db.commit()
    if settings.bootstrap_admin_password and settings.bootstrap_admin_emails:
        from .models import Role, User
        from .passwords import hash_password
        admin_email=next(iter(settings.email_set(settings.bootstrap_admin_emails)))
        desired_username=settings.bootstrap_admin_username.strip().lower()
        with SessionLocal() as db:
            admin=db.scalar(select(User).where(User.email==admin_email))
            username_owner=None
            if desired_username:
                username_owner=db.scalar(select(User).where(func.lower(User.username)==desired_username))
            if not admin:
                admin=User(email=admin_email,name="System Administrator",role=Role.ADMIN.value,is_active=True)
                db.add(admin)
            # Never steal a username from an existing migrated account. This can
            # happen when BOOTSTRAP_ADMIN_EMAILS differs between environments.
            if desired_username and (not username_owner or username_owner.id==admin.id):
                admin.username=desired_username
            admin.role=Role.ADMIN.value;admin.is_active=True
            if not admin.password_hash:
                admin.password_hash=hash_password(settings.bootstrap_admin_password)
            db.commit()
