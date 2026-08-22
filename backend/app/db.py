from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=20, fast_executemany=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column(conn, table: str, name: str, sql_type: str) -> None:
    conn.execute(text(f"IF COL_LENGTH('{table}', '{name}') IS NULL ALTER TABLE [{table}] ADD [{name}] {sql_type}"))


def _create_fulltext(conn) -> None:
    conn.execute(text("IF NOT EXISTS (SELECT 1 FROM sys.fulltext_catalogs WHERE name='masterdata_fts') CREATE FULLTEXT CATALOG masterdata_fts AS DEFAULT"))
    conn.execute(text("IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('items') AND name='ux_items_fts_key') CREATE UNIQUE INDEX ux_items_fts_key ON items(id)"))
    conn.execute(text("IF NOT EXISTS (SELECT 1 FROM sys.fulltext_indexes WHERE object_id=OBJECT_ID('items')) CREATE FULLTEXT INDEX ON items(search_text LANGUAGE 0, code LANGUAGE 0, name LANGUAGE 0, name2 LANGUAGE 0) KEY INDEX ux_items_fts_key WITH CHANGE_TRACKING AUTO"))


def init_db():
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        item_columns = {
            "new_code": "NVARCHAR(100) NULL", "old_code": "NVARCHAR(100) NULL", "parent_id": "INT NULL",
            "is_group": "BIT NOT NULL DEFAULT 0", "source_extra_1": "NVARCHAR(MAX) NULL", "source_extra_2": "NVARCHAR(MAX) NULL",
            "name2": "NVARCHAR(MAX) NULL", "item_custom": "NVARCHAR(MAX) NULL", "is_customs": "BIT NOT NULL DEFAULT 0",
            "is_item_with_color": "BIT NOT NULL DEFAULT 0", "is_item_with_size": "BIT NOT NULL DEFAULT 0",
            "is_item_with_art": "BIT NOT NULL DEFAULT 0", "is_item_with_product_cost_id": "BIT NOT NULL DEFAULT 0",
            "is_item_with_biz_doc_id_c2": "BIT NOT NULL DEFAULT 0", "is_item_with_symmetrical": "BIT NOT NULL DEFAULT 0",
            "is_item_with_color_product": "BIT NOT NULL DEFAULT 0", "product_cost_info": "NVARCHAR(MAX) NULL",
            "product_item_code": "NVARCHAR(100) NULL", "branch_code": "NVARCHAR(100) NULL", "is_material": "BIT NOT NULL DEFAULT 0",
            "source_created_by": "INT NULL", "source_created_at": "DATETIMEOFFSET NULL", "source_modified_by": "INT NULL",
            "source_select_key": "BIT NULL", "extra_data": "NVARCHAR(MAX) NULL",
        }
        request_columns = {
            "requester_name": "NVARCHAR(255) NOT NULL DEFAULT ''", "department": "NVARCHAR(255) NOT NULL DEFAULT ''",
            "item_type_name": "NVARCHAR(100) NULL", "parent_code": "NVARCHAR(100) NULL", "kind_code": "NVARCHAR(100) NULL",
            "brand": "NVARCHAR(255) NULL", "customer_code": "NVARCHAR(100) NULL", "branch_code": "NVARCHAR(100) NULL",
            "is_material": "BIT NOT NULL DEFAULT 0", "with_color": "BIT NOT NULL DEFAULT 0", "with_size": "BIT NOT NULL DEFAULT 0",
            "with_art": "BIT NOT NULL DEFAULT 0", "submitted_at": "DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET()",
            "accounting_note": "NVARCHAR(MAX) NULL", "code_issued_at": "DATETIMEOFFSET NULL",
        }
        for name, sql_type in item_columns.items():
            _add_column(conn, "items", name, sql_type)
        for name, sql_type in request_columns.items():
            _add_column(conn, "material_requests", name, sql_type)
        for name, sql_type in {"is_active": "BIT NOT NULL DEFAULT 1", "username": "NVARCHAR(100) NULL", "password_hash": "NVARCHAR(MAX) NULL", "token_version": "INT NOT NULL DEFAULT 0"}.items():
            _add_column(conn, "users", name, sql_type)

        conn.execute(text("UPDATE material_requests SET code_issued_at=updated_at WHERE status='COMPLETED' AND code_issued_at IS NULL"))
        conn.execute(text("IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('material_requests') AND name='ix_material_requests_code_issued_at') CREATE INDEX ix_material_requests_code_issued_at ON material_requests(code_issued_at DESC)"))
        conn.execute(text("IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('users') AND name='ux_users_username') CREATE UNIQUE INDEX ux_users_username ON users(username) WHERE username IS NOT NULL"))
        conn.execute(text("IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('items') AND name='ux_items_code') CREATE UNIQUE INDEX ux_items_code ON items(code)"))
        expected = set(item_columns) | {"id", "code", "name", "item_type_name", "parent_code", "item_group_code", "kind_code", "customer_code", "unit_price", "is_active", "search_text", "source_modified_at"}
        actual = set(conn.execute(text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='items'")).scalars())
        missing = expected - actual
        if missing:
            raise RuntimeError(f"Migration items chưa đầy đủ, thiếu cột: {', '.join(sorted(missing))}")

    # SQL Server yêu cầu một số lệnh Full-Text chạy ngoài user transaction.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        _create_fulltext(conn)

    if settings.bootstrap_admin_password and settings.bootstrap_admin_emails:
        from .models import Role, User
        from .passwords import hash_password
        admin_email = next(iter(settings.email_set(settings.bootstrap_admin_emails)))
        with SessionLocal() as db:
            admin = db.scalar(select(User).where(User.email == admin_email))
            if not admin:
                admin = User(email=admin_email, name="System Administrator", role=Role.ADMIN.value, is_active=True)
                db.add(admin)
            admin.username = settings.bootstrap_admin_username.strip().lower()
            admin.role = Role.ADMIN.value
            admin.is_active = True
            if not admin.password_hash:
                admin.password_hash = hash_password(settings.bootstrap_admin_password)
            db.commit()
