from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=20)
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
            "item_type_name":"VARCHAR(100)", "parent_code":"VARCHAR(100)", "kind_code":"VARCHAR(100)",
            "customer_code":"VARCHAR(100)", "branch_code":"VARCHAR(100)", "is_material":"BOOLEAN NOT NULL DEFAULT FALSE",
            "with_color":"BOOLEAN NOT NULL DEFAULT FALSE", "with_size":"BOOLEAN NOT NULL DEFAULT FALSE", "with_art":"BOOLEAN NOT NULL DEFAULT FALSE",
            "submitted_at":"TIMESTAMPTZ NOT NULL DEFAULT NOW()", "accounting_note":"TEXT"
        }
        for name, sql_type in item_columns.items(): conn.execute(text(f"ALTER TABLE items ADD COLUMN IF NOT EXISTS {name} {sql_type}"))
        for name, sql_type in request_columns.items(): conn.execute(text(f"ALTER TABLE material_requests ADD COLUMN IF NOT EXISTS {name} {sql_type}"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_items_code ON items(code)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_items_fts ON items USING GIN (to_tsvector('simple', search_text))"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_items_trgm ON items USING GIN (search_text gin_trgm_ops)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_items_code_trgm ON items USING GIN (code gin_trgm_ops)"))
        expected=set(item_columns)|{"id","code","name","item_type_name","parent_code","item_group_code","kind_code","customer_code","unit_price","is_active","search_text","source_modified_at"}
        actual=set(conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='items'")).scalars())
        missing=expected-actual
        if missing:
            raise RuntimeError(f"Migration items chưa đầy đủ, thiếu cột: {', '.join(sorted(missing))}")
