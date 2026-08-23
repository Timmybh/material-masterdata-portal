import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class Role(str, enum.Enum):
    USER="USER"; MASTERDATA="MASTERDATA"; ACCOUNTING="ACCOUNTING"; ADMIN="ADMIN"
class RequestStatus(str, enum.Enum):
    SUBMITTED="SUBMITTED"; MASTERDATA_RETURNED="MASTERDATA_RETURNED"; MASTERDATA_APPROVED="MASTERDATA_APPROVED"; ACCOUNTING_RETURNED="ACCOUNTING_RETURNED"; COMPLETED="COMPLETED"

class User(Base):
    __tablename__="users"
    id: Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    email: Mapped[str]=mapped_column(String(320),unique=True,index=True)
    username: Mapped[str|None]=mapped_column(String(100),unique=True,index=True,nullable=True)
    password_hash: Mapped[str|None]=mapped_column(Text,nullable=True)
    name: Mapped[str]=mapped_column(String(255),default="")
    picture: Mapped[str|None]=mapped_column(Text,nullable=True)
    role: Mapped[str]=mapped_column(String(32),default=Role.USER.value,index=True)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    token_version: Mapped[int]=mapped_column(Integer,default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)

class UserAudit(Base):
    __tablename__="user_audits"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id"),index=True)
    actor_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id"),index=True)
    action: Mapped[str]=mapped_column(String(100),index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,index=True)

class MaterialType(Base):
    __tablename__="material_types"
    code: Mapped[str]=mapped_column(String(100),primary_key=True)
    name: Mapped[str]=mapped_column(String(255),unique=True,index=True)

class ItemGroup(Base):
    __tablename__="item_groups"
    code: Mapped[str]=mapped_column(String(100),primary_key=True)
    name: Mapped[str]=mapped_column(String(255),unique=True,index=True)

class Item(Base):
    __tablename__="items"
    id: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=False)
    new_code: Mapped[str|None]=mapped_column(String(100),nullable=True,index=True)
    old_code: Mapped[str|None]=mapped_column(String(100),nullable=True,index=True)
    code: Mapped[str]=mapped_column(String(100),unique=True,index=True)
    parent_id: Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
    is_group: Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    source_extra_1: Mapped[str|None]=mapped_column(Text,nullable=True)
    source_extra_2: Mapped[str|None]=mapped_column(Text,nullable=True)
    name: Mapped[str]=mapped_column(Text,index=True)
    item_type_name: Mapped[str]=mapped_column(String(100),index=True)
    name2: Mapped[str|None]=mapped_column(Text,nullable=True)
    item_custom: Mapped[str|None]=mapped_column(Text,nullable=True)
    is_customs: Mapped[bool]=mapped_column(Boolean,default=False)
    is_item_with_color: Mapped[bool]=mapped_column(Boolean,default=False)
    is_item_with_size: Mapped[bool]=mapped_column(Boolean,default=False)
    is_item_with_art: Mapped[bool]=mapped_column(Boolean,default=False)
    is_item_with_product_cost_id: Mapped[bool]=mapped_column(Boolean,default=False)
    is_item_with_biz_doc_id_c2: Mapped[bool]=mapped_column(Boolean,default=False)
    is_item_with_symmetrical: Mapped[bool]=mapped_column(Boolean,default=False)
    is_item_with_color_product: Mapped[bool]=mapped_column(Boolean,default=False)
    parent_code: Mapped[str|None]=mapped_column(String(100),nullable=True,index=True)
    item_group_code: Mapped[str|None]=mapped_column(String(100),nullable=True,index=True)
    kind_code: Mapped[str|None]=mapped_column(String(100),nullable=True,index=True)
    customer_code: Mapped[str|None]=mapped_column(String(100),nullable=True,index=True)
    product_cost_info: Mapped[str|None]=mapped_column(Text,nullable=True)
    product_item_code: Mapped[str|None]=mapped_column(String(100),nullable=True)
    branch_code: Mapped[str|None]=mapped_column(String(100),nullable=True,index=True)
    is_material: Mapped[bool]=mapped_column(Boolean,default=False)
    unit_price: Mapped[float|None]=mapped_column(Numeric(18,4),nullable=True)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    source_created_by: Mapped[int|None]=mapped_column(Integer,nullable=True)
    source_created_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    source_modified_by: Mapped[int|None]=mapped_column(Integer,nullable=True)
    source_modified_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    source_select_key: Mapped[bool|None]=mapped_column(Boolean,nullable=True)
    search_text: Mapped[str]=mapped_column(Text,default="")
    extra_data: Mapped[str|None]=mapped_column(Text,nullable=True)
    __table_args__=(Index("ix_items_parent_group","parent_id","is_group"),Index("ix_items_type_group","item_type_name","item_group_code"))

class AutoImportConfig(Base):
    __tablename__="auto_import_config"
    id: Mapped[int]=mapped_column(Integer,primary_key=True,default=1)
    enabled: Mapped[bool]=mapped_column(Boolean,default=True)
    file_path: Mapped[str]=mapped_column(Text,default="/data/Danh muc vat tu.xlsx")
    hour: Mapped[int]=mapped_column(Integer,default=19)
    minute: Mapped[int]=mapped_column(Integer,default=0)
    timezone: Mapped[str]=mapped_column(String(100),default="Asia/Ho_Chi_Minh")
    is_running: Mapped[bool]=mapped_column(Boolean,default=False)
    last_trigger: Mapped[str|None]=mapped_column(String(20),nullable=True)
    last_started_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    last_completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    last_status: Mapped[str|None]=mapped_column(String(20),nullable=True)
    last_imported: Mapped[int|None]=mapped_column(Integer,nullable=True)
    last_skipped: Mapped[int|None]=mapped_column(Integer,nullable=True)
    last_error: Mapped[str|None]=mapped_column(Text,nullable=True)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,onupdate=datetime.utcnow)

class MaterialRequest(Base):
    __tablename__="material_requests"
    id: Mapped[uuid.UUID]=mapped_column(primary_key=True,default=uuid.uuid4)
    requester_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id"),index=True)
    requester_name: Mapped[str]=mapped_column(String(255),default="")
    department: Mapped[str]=mapped_column(String(255),default="")
    item_name: Mapped[str]=mapped_column(String(500)); unit: Mapped[str]=mapped_column(String(100)); brand: Mapped[str|None]=mapped_column(String(255),nullable=True)
    specification: Mapped[str|None]=mapped_column(Text,nullable=True); technical_specs: Mapped[str|None]=mapped_column(Text,nullable=True)
    purpose: Mapped[str|None]=mapped_column(Text,nullable=True); notes: Mapped[str|None]=mapped_column(Text,nullable=True)
    item_type_name: Mapped[str|None]=mapped_column(String(100),nullable=True); parent_code: Mapped[str|None]=mapped_column(String(100),nullable=True)
    item_group: Mapped[str|None]=mapped_column(String(200),nullable=True); classification: Mapped[str|None]=mapped_column(String(200),nullable=True)
    kind_code: Mapped[str|None]=mapped_column(String(100),nullable=True); customer_code: Mapped[str|None]=mapped_column(String(100),nullable=True)
    branch_code: Mapped[str|None]=mapped_column(String(100),nullable=True); is_material: Mapped[bool]=mapped_column(Boolean,default=False)
    with_color: Mapped[bool]=mapped_column(Boolean,default=False); with_size: Mapped[bool]=mapped_column(Boolean,default=False); with_art: Mapped[bool]=mapped_column(Boolean,default=False)
    result_item_code: Mapped[str|None]=mapped_column(String(100),nullable=True)
    accounting_note: Mapped[str|None]=mapped_column(Text,nullable=True)
    status: Mapped[str]=mapped_column(String(40),default=RequestStatus.SUBMITTED.value,index=True)
    returned_reason: Mapped[str|None]=mapped_column(Text,nullable=True)
    submitted_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
    code_issued_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,index=True)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,onupdate=datetime.utcnow)
    requester: Mapped[User]=relationship(); audits: Mapped[list["RequestAudit"]]=relationship(back_populates="request",cascade="all, delete-orphan")

class RequestAudit(Base):
    __tablename__="request_audits"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    request_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("material_requests.id"),index=True)
    actor_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id")); action: Mapped[str]=mapped_column(String(100))
    from_status: Mapped[str|None]=mapped_column(String(40),nullable=True); to_status: Mapped[str|None]=mapped_column(String(40),nullable=True)
    note: Mapped[str|None]=mapped_column(Text,nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
    request: Mapped[MaterialRequest]=relationship(back_populates="audits"); actor: Mapped[User]=relationship()
