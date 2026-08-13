from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

class GoogleAuthIn(BaseModel): credential: str
class DevAuthIn(BaseModel): email: EmailStr; name: str="Dev User"; role: str="USER"
class UserOut(BaseModel):
    id: UUID; email: str; name: str; picture: str|None=None; role: str; is_active: bool=True
    model_config={"from_attributes":True}
class AuthOut(BaseModel): access_token: str; token_type: str="bearer"; user: UserOut
class ItemOut(BaseModel):
    id:int; new_code:str|None=None; old_code:str|None=None; code:str; parent_id:int|None=None; is_group:bool; name:str; item_type_name:str
    name2:str|None=None; item_custom:str|None=None; is_customs:bool; is_item_with_color:bool; is_item_with_size:bool; is_item_with_art:bool
    is_item_with_product_cost_id:bool; is_item_with_biz_doc_id_c2:bool; is_item_with_symmetrical:bool; is_item_with_color_product:bool
    parent_code:str|None=None; item_group_code:str|None=None; kind_code:str|None=None; customer_code:str|None=None; product_cost_info:str|None=None
    product_item_code:str|None=None; branch_code:str|None=None; is_material:bool; unit_price:Decimal|None=None; is_active:bool
    source_created_by:int|None=None; source_created_at:datetime|None=None; source_modified_by:int|None=None; source_modified_at:datetime|None=None; score:float|None=None
    model_config={"from_attributes":True}
class ItemSearchOut(BaseModel): items:list[ItemOut]; total:int; limit:int; query:str
class RequestFields(BaseModel):
    item_name:str=Field(min_length=2,max_length=500); unit:str=Field(min_length=1,max_length=100)
    specification:str|None=None; technical_specs:str|None=None; purpose:str|None=None; notes:str|None=None
    item_type_name:str|None=None; parent_code:str|None=None; item_group:str|None=None; classification:str|None=None
    kind_code:str|None=None; customer_code:str|None=None; branch_code:str|None=None
    is_material:bool=False; with_color:bool=False; with_size:bool=False; with_art:bool=False
class RequestCreate(RequestFields): pass
class RequestUpdate(RequestFields): pass
class MasterdataUpdate(BaseModel):
    item_name:str|None=None; unit:str|None=None; specification:str|None=None; technical_specs:str|None=None; purpose:str|None=None; notes:str|None=None
    item_type_name:str|None=None; parent_code:str|None=None; item_group:str|None=None; classification:str|None=None; kind_code:str|None=None
    customer_code:str|None=None; branch_code:str|None=None; is_material:bool|None=None; with_color:bool|None=None; with_size:bool|None=None; with_art:bool|None=None
class ReasonIn(BaseModel): reason:str=Field(min_length=3)
class CompleteIn(BaseModel): item_code:str=Field(min_length=1,max_length=100)
class UserRoleUpdate(BaseModel): role:str; is_active:bool|None=None
class RequestOut(RequestFields):
    id:UUID; result_item_code:str|None; status:str; returned_reason:str|None; submitted_at:datetime; created_at:datetime; updated_at:datetime; requester:UserOut
    model_config={"from_attributes":True}
