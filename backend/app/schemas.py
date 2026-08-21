from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_optional_password(value: str) -> str:
    if value and len(value) < 8:
        raise ValueError("Mật khẩu phải có ít nhất 8 ký tự hoặc để trống")
    return value

class GoogleAuthIn(BaseModel): credential: str
class DevAuthIn(BaseModel): email: EmailStr; name: str="Dev User"; role: str="USER"
class PasswordLoginIn(BaseModel):
    identifier:str=Field(min_length=1,max_length=320)
    password:str=Field(default="",max_length=256)
class UserOut(BaseModel):
    id: UUID; email: str; username:str|None=None; name: str; picture: str|None=None; role: str; is_active: bool=True
    model_config={"from_attributes":True}
class AuthOut(BaseModel): access_token: str; token_type: str="bearer"; user: UserOut
class ItemOut(BaseModel):
    id:int; new_code:str|None=None; old_code:str|None=None; code:str; parent_id:int|None=None; is_group:bool; source_extra_1:str|None=None; source_extra_2:str|None=None; name:str; item_type_name:str
    name2:str|None=None; item_custom:str|None=None; is_customs:bool; is_item_with_color:bool; is_item_with_size:bool; is_item_with_art:bool
    is_item_with_product_cost_id:bool; is_item_with_biz_doc_id_c2:bool; is_item_with_symmetrical:bool; is_item_with_color_product:bool
    parent_code:str|None=None; item_group_code:str|None=None; kind_code:str|None=None; customer_code:str|None=None; product_cost_info:str|None=None
    product_item_code:str|None=None; branch_code:str|None=None; is_material:bool; unit_price:Decimal|None=None; is_active:bool
    source_created_by:int|None=None; source_created_at:datetime|None=None; source_modified_by:int|None=None; source_modified_at:datetime|None=None; source_select_key:bool|None=None; score:float|None=None
    model_config={"from_attributes":True}
class ItemSearchOut(BaseModel): items:list[ItemOut]; total:int; limit:int; query:str
class RequestFields(BaseModel):
    requester_name:str=Field(min_length=2,max_length=255); department:str=Field(min_length=1,max_length=255)
    item_name:str=Field(min_length=2,max_length=500); unit:str=Field(min_length=1,max_length=100); brand:str|None=Field(default=None,max_length=255)
    specification:str|None=None; technical_specs:str|None=None; purpose:str|None=None; notes:str|None=None
    item_type_name:str|None=None; parent_code:str|None=None; item_group:str|None=None; classification:str|None=None
    kind_code:str|None=None; customer_code:str|None=None; branch_code:str|None=None
    is_material:bool=False; with_color:bool=False; with_size:bool=False; with_art:bool=False
class RequestCreate(RequestFields): pass
class RequestUpdate(RequestFields): pass
class MasterdataUpdate(BaseModel):
    requester_name:str|None=Field(default=None,min_length=2,max_length=255); department:str|None=Field(default=None,min_length=1,max_length=255)
    item_name:str|None=None; unit:str|None=None; brand:str|None=Field(default=None,max_length=255); specification:str|None=None; technical_specs:str|None=None; purpose:str|None=None; notes:str|None=None
    item_type_name:str|None=None; parent_code:str|None=None; item_group:str|None=None; classification:str|None=None; kind_code:str|None=None
    customer_code:str|None=None; branch_code:str|None=None; is_material:bool|None=None; with_color:bool|None=None; with_size:bool|None=None; with_art:bool|None=None
class ReasonIn(BaseModel): reason:str=Field(min_length=3)
class CompleteIn(BaseModel):
    item_code:str=Field(min_length=1,max_length=100)
    note:str|None=Field(default=None,max_length=2000)
class DuplicateCheckIn(BaseModel):
    item_name:str=Field(min_length=2,max_length=500)
    specification:str|None=Field(default=None,max_length=4000)
    purpose:str|None=Field(default=None,max_length=4000)
    limit:int=Field(default=8,ge=1,le=20)
class DuplicateCandidateOut(BaseModel):
    code:str; name:str; similarity:float; reason:str|None=None; duplicate_risk:str="POSSIBLE"
class DuplicateCheckOut(BaseModel):
    ai_used:bool; summary:str; candidates:list[DuplicateCandidateOut]
class NameSuggestionIn(BaseModel):
    item_name:str=Field(min_length=2,max_length=500)
    specification:str|None=Field(default=None,max_length=4000)
    technical_specs:str|None=Field(default=None,max_length=4000)
    purpose:str|None=Field(default=None,max_length=4000)
class NameSuggestionOut(BaseModel):
    suggested_name:str=Field(min_length=2,max_length=500)
    explanation:str
class UserRoleUpdate(BaseModel):
    name:str|None=Field(default=None,min_length=2,max_length=255)
    email:EmailStr|None=None
    username:str|None=Field(default=None,min_length=1,max_length=100,pattern=r"^[A-Za-z0-9._-]+$")
    role:str; is_active:bool|None=None
class AdminUserCreate(BaseModel):
    email:EmailStr; username:str=Field(min_length=1,max_length=100,pattern=r"^[A-Za-z0-9._-]+$"); password:str=Field(default="",max_length=256)
    name:str=Field(min_length=2,max_length=255); role:str="USER"; is_active:bool=True
    _validate_password=field_validator("password")(validate_optional_password)
class AdminPasswordReset(BaseModel):
    password:str=Field(default="",max_length=256)
    password_confirmation:str=Field(default="",max_length=256)
    _validate_passwords=field_validator("password","password_confirmation")(validate_optional_password)
class CatalogIn(BaseModel):
    code:str=Field(min_length=1,max_length=100)
    name:str=Field(min_length=1,max_length=255)
class CatalogOut(CatalogIn):
    model_config={"from_attributes":True}
class RequestOut(RequestFields):
    id:UUID; result_item_code:str|None; accounting_note:str|None=None; status:str; returned_reason:str|None; submitted_at:datetime; code_issued_at:datetime|None=None; created_at:datetime; updated_at:datetime; requester:UserOut
    model_config={"from_attributes":True}
