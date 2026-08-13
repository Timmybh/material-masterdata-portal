import asyncio
import base64
import hashlib
import hmac
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from secrets import token_urlsafe
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+asyncpg://postgres:12345678@db:5432/masterdata')
JWT_SECRET = os.getenv('JWT_SECRET', 'change-me-v1-5')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_HOURS = 12
SMTP_HOST = os.getenv('SMTP_HOST', '').strip()
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '').strip()
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER or 'no-reply@dovitec.local')
SMTP_STARTTLS = os.getenv('SMTP_STARTTLS', 'true').lower() in {'1', 'true', 'yes', 'on'}

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
security = HTTPBearer(auto_error=False)
app = FastAPI(title='Material Masterdata Portal API', version='1.5.1')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=False, allow_methods=['*'], allow_headers=['*'])
ROLES = {'USER', 'MASTERDATA', 'ACCOUNTING', 'ADMIN'}


class LoginPayload(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    email: str = Field(max_length=255)
    full_name: str = Field(min_length=2, max_length=255)
    role: str
    password: str = Field(min_length=8, max_length=128)
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None


class MaterialRequestCreate(BaseModel):
    proposed_name: str = Field(min_length=2, max_length=500)
    supplier_material_code: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=4000)
    unit: str | None = Field(default=None, max_length=50)
    material_group: str | None = Field(default=None, max_length=100)


class MaterialRequestUpdate(BaseModel):
    proposed_name: str = Field(min_length=2, max_length=500)
    supplier_material_code: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=4000)
    unit: str | None = Field(default=None, max_length=50)
    material_group: str | None = Field(default=None, max_length=100)


class WorkflowTransition(BaseModel):
    action: str = Field(max_length=50)
    note: str | None = Field(default=None, max_length=4000)
    material_code: str | None = Field(default=None, max_length=100)


def hash_password(password: str) -> str:
    iterations = 200000
    salt = token_urlsafe(12)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), iterations)
    return f'pbkdf2_sha256${iterations}${salt}${base64.b64encode(digest).decode()}'


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        scheme, iterations, salt, digest = encoded.split('$', 3)
        if scheme != 'pbkdf2_sha256':
            return False
        candidate = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(base64.b64encode(candidate).decode(), digest)
    except Exception:
        return False


def create_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user['id']), 'email': user['email'], 'role': user['role'], 'iat': now, 'exp': now + timedelta(hours=JWT_EXPIRE_HOURS)}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def public_user(row) -> dict:
    return {'id': row['id'], 'email': row['email'], 'full_name': row['full_name'], 'role': row['role'], 'is_active': row['is_active']}


async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail='Chưa đăng nhập')
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload['sub'])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail='Phiên đăng nhập không hợp lệ hoặc đã hết hạn')
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT id,email,full_name,role,is_active FROM users WHERE id=:id LIMIT 1'), {'id': user_id})
        row = result.mappings().one_or_none()
    if not row or not row['is_active']:
        raise HTTPException(status_code=401, detail='Tài khoản không tồn tại hoặc đã bị khóa')
    return dict(row)


def require_role(*roles):
    async def dependency(user: dict = Depends(current_user)):
        if user['role'] not in roles:
            raise HTTPException(status_code=403, detail='Bạn không có quyền thực hiện chức năng này')
        return user
    return dependency


def request_select_sql(where_clause: str = '') -> str:
    return f'''SELECT r.id,r.request_no,r.requester_id,u.email requester_email,u.full_name requester_name,
      r.proposed_name,r.supplier_material_code,r.description,r.unit,r.material_group,r.status,r.masterdata_note,r.accounting_note,
      r.result_material_code,r.created_at,r.updated_at
      FROM material_requests r LEFT JOIN users u ON u.id=r.requester_id {where_clause}'''


def full_material_email_html(request: dict, title: str, message: str) -> str:
    def v(key):
        value = request.get(key)
        return str(value) if value not in (None, '') else '-'
    return f'''<div style="font-family:Aptos,Arial,sans-serif;color:#172033;line-height:1.5">
      <h2>{title}</h2><p>{message}</p>
      <table style="border-collapse:collapse;width:100%;max-width:760px">
      <tr><td><b>Số yêu cầu</b></td><td>{v('request_no')}</td></tr>
      <tr><td><b>Mã hàng mới</b></td><td>{v('result_material_code')}</td></tr>
      <tr><td><b>Mã vật tư Nhà cung cấp</b></td><td>{v('supplier_material_code')}</td></tr>
      <tr><td><b>Tên vật tư</b></td><td>{v('proposed_name')}</td></tr>
      <tr><td><b>Mô tả / quy cách</b></td><td>{v('description')}</td></tr>
      <tr><td><b>Đơn vị tính</b></td><td>{v('unit')}</td></tr>
      <tr><td><b>Nhóm vật tư</b></td><td>{v('material_group')}</td></tr>
      <tr><td><b>Người tạo</b></td><td>{v('requester_name')} ({v('requester_email')})</td></tr>
      <tr><td><b>Ghi chú Masterdata</b></td><td>{v('masterdata_note')}</td></tr>
      <tr><td><b>Ghi chú Kế toán</b></td><td>{v('accounting_note')}</td></tr>
      <tr><td><b>Trạng thái</b></td><td>{v('status')}</td></tr>
      </table></div>'''


def _send_smtp(recipient: str, subject: str, html: str):
    msg = EmailMessage()
    msg['From'] = SMTP_FROM
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.set_content('Email này cần trình đọc HTML để hiển thị đầy đủ thông tin.')
    msg.add_alternative(html, subtype='html')
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        if SMTP_STARTTLS:
            smtp.starttls()
        if SMTP_USER:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)


async def send_and_log_email(request_id: int | None, recipient: str, subject: str, email_type: str, html: str):
    if not recipient:
        return
    status = 'SKIPPED'
    error_message = None
    if SMTP_HOST:
        try:
            await asyncio.to_thread(_send_smtp, recipient, subject, html)
            status = 'SENT'
        except Exception as exc:
            status = 'FAILED'
            error_message = str(exc)[:2000]
    else:
        error_message = 'SMTP_HOST chưa được cấu hình; email được ghi log nhưng chưa gửi.'
    async with engine.begin() as conn:
        await conn.execute(text('''INSERT INTO email_logs(request_id,recipient,subject,email_type,status,error_message)
          VALUES(:rid,:recipient,:subject,:etype,:status,:error)'''),
          {'rid': request_id, 'recipient': recipient, 'subject': subject, 'etype': email_type, 'status': status, 'error': error_message})


async def role_emails(role: str) -> list[str]:
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT email FROM users WHERE role=:role AND is_active=TRUE ORDER BY id'), {'role': role})
        return [r['email'] for r in result.mappings().all()]


async def notify_stage(request: dict, stage: str, actor_note: str | None = None):
    rid = request['id']
    requester = request.get('requester_email')
    if stage == 'CREATED':
        html = full_material_email_html(request, 'Đã tiếp nhận yêu cầu tạo mã', 'Yêu cầu đã được gửi đến Nhân sự phụ trách Masterdata.')
        await send_and_log_email(rid, requester, f"[{request['request_no']}] Đã tiếp nhận yêu cầu", 'REQUEST_CREATED', html)
        for email in await role_emails('MASTERDATA'):
            await send_and_log_email(rid, email, f"[{request['request_no']}] Có yêu cầu chờ Masterdata duyệt", 'MASTERDATA_PENDING', html)
    elif stage == 'MASTERDATA_APPROVED':
        html = full_material_email_html(request, 'Masterdata đã duyệt và cấp mã', 'Yêu cầu đã được Masterdata duyệt, mã hàng mới đã được xác lập và chuyển Kế toán phê duyệt cuối.')
        await send_and_log_email(rid, requester, f"[{request['request_no']}] Masterdata đã duyệt", 'MASTERDATA_APPROVED', html)
        for email in await role_emails('ACCOUNTING'):
            await send_and_log_email(rid, email, f"[{request['request_no']}] Chờ Kế toán phê duyệt cuối", 'ACCOUNTING_PENDING', html)
    elif stage == 'RETURNED':
        html = full_material_email_html(request, 'Yêu cầu đã được trả lại', f"Lý do: {actor_note or '-'}")
        await send_and_log_email(rid, requester, f"[{request['request_no']}] Yêu cầu được trả lại để cập nhật", 'RETURNED_TO_REQUESTER', html)
    elif stage == 'RESUBMITTED':
        html = full_material_email_html(request, 'Yêu cầu đã được gửi duyệt lại', 'Yêu cầu đã quay lại hàng chờ Masterdata.')
        await send_and_log_email(rid, requester, f"[{request['request_no']}] Đã gửi duyệt lại", 'RESUBMITTED', html)
        for email in await role_emails('MASTERDATA'):
            await send_and_log_email(rid, email, f"[{request['request_no']}] Yêu cầu được gửi duyệt lại", 'MASTERDATA_PENDING', html)
    elif stage == 'COMPLETED':
        html = full_material_email_html(request, 'Kết quả tạo mã vật tư', 'Kế toán đã phê duyệt cuối. Dưới đây là toàn bộ thông tin vật tư và mã hàng mới.')
        await send_and_log_email(rid, requester, f"[{request['request_no']}] Hoàn tất - Mã hàng mới {request.get('result_material_code') or ''}", 'FINAL_RESULT', html)
        for email in await role_emails('MASTERDATA'):
            await send_and_log_email(rid, email, f"[{request['request_no']}] Kế toán đã phê duyệt - Hoàn tất", 'FINAL_RESULT_COPY', html)


@app.get('/health')
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        db = 'ok'
    except Exception:
        db = 'error'
    return {'status': 'ok' if db == 'ok' else 'degraded', 'database': db, 'service': 'material-masterdata-portal', 'version': '1.5.1', 'smtp_configured': bool(SMTP_HOST)}


@app.post('/api/v1/auth/login')
async def login(payload: LoginPayload):
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT id,email,full_name,role,is_active,password_hash FROM users WHERE lower(email)=lower(:email) LIMIT 1'), {'email': payload.email.strip()})
        row = result.mappings().one_or_none()
    if not row or not row['is_active'] or not verify_password(payload.password, row['password_hash']):
        raise HTTPException(status_code=401, detail='Email hoặc mật khẩu không đúng')
    user = dict(row)
    return {'access_token': create_token(user), 'token_type': 'bearer', 'user': public_user(user)}


@app.get('/api/v1/auth/me')
async def me(user: dict = Depends(current_user)):
    return user


@app.get('/api/v1/users')
async def list_users(_: dict = Depends(require_role('ADMIN'))):
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT id,email,full_name,role,is_active,created_at,updated_at FROM users ORDER BY full_name,email'))
        return {'items': [dict(r) for r in result.mappings().all()]}


@app.post('/api/v1/users', status_code=201)
async def create_user(payload: UserCreate, _: dict = Depends(require_role('ADMIN'))):
    role = payload.role.upper().strip()
    if role not in ROLES:
        raise HTTPException(status_code=400, detail='Vai trò không hợp lệ')
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text('''INSERT INTO users(email,full_name,role,is_active,password_hash,updated_at)
              VALUES(:email,:full_name,:role,:active,:password,NOW()) RETURNING id,email,full_name,role,is_active,created_at,updated_at'''),
              {'email': payload.email.strip().lower(), 'full_name': payload.full_name.strip(), 'role': role, 'active': payload.is_active, 'password': hash_password(payload.password)})
            return dict(result.mappings().one())
    except Exception as exc:
        if 'unique' in str(exc).lower():
            raise HTTPException(status_code=409, detail='Email đã tồn tại')
        raise


@app.patch('/api/v1/users/{user_id}')
async def update_user(user_id: int, payload: UserUpdate, admin: dict = Depends(require_role('ADMIN'))):
    updates = ['updated_at=NOW()']; params = {'id': user_id}
    if payload.full_name is not None: updates.append('full_name=:full_name'); params['full_name'] = payload.full_name.strip()
    if payload.role is not None:
        role = payload.role.upper().strip()
        if role not in ROLES: raise HTTPException(status_code=400, detail='Vai trò không hợp lệ')
        updates.append('role=:role'); params['role'] = role
    if payload.password is not None: updates.append('password_hash=:password'); params['password'] = hash_password(payload.password)
    if payload.is_active is not None:
        if user_id == admin['id'] and payload.is_active is False: raise HTTPException(status_code=400, detail='Không thể tự khóa tài khoản quản trị đang đăng nhập')
        updates.append('is_active=:active'); params['active'] = payload.is_active
    async with engine.begin() as conn:
        result = await conn.execute(text(f'''UPDATE users SET {','.join(updates)} WHERE id=:id
          RETURNING id,email,full_name,role,is_active,created_at,updated_at'''), params)
        row = result.mappings().one_or_none()
    if not row: raise HTTPException(status_code=404, detail='Không tìm thấy người dùng')
    return dict(row)


@app.get('/api/v1/sync-status')
async def get_sync_status(_: dict = Depends(current_user)):
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT source_name,last_synced_at,row_count,status,message,updated_at FROM sync_status WHERE source_name='BRAVO'"))
        row = result.mappings().one_or_none()
    return dict(row) if row else {'source_name': 'BRAVO', 'last_synced_at': None, 'row_count': 0, 'status': 'UNKNOWN'}


@app.get('/api/v1/materials/search')
async def search_materials(q: str = Query(default='', max_length=200), limit: int = Query(default=20, ge=1, le=100), _: dict = Depends(current_user)):
    keyword = q.strip()
    where = '''(:keyword='' OR to_tsvector('simple',coalesce(material_code,'')||' '||coalesce(material_name,'')||' '||coalesce(description,'')) @@ plainto_tsquery('simple',:keyword)
      OR material_code ILIKE :pattern OR material_name ILIKE :pattern OR coalesce(description,'') ILIKE :pattern)'''
    params = {'keyword': keyword, 'pattern': f'%{keyword}%', 'limit': limit}
    async with engine.connect() as conn:
        total_result = await conn.execute(text(f'SELECT COUNT(*) FROM materials WHERE {where}'), params)
        total = total_result.scalar_one()
        result = await conn.execute(text(f'''SELECT id,material_code,material_name,description,unit,material_group,created_at FROM materials
          WHERE {where} ORDER BY material_code LIMIT :limit'''), params)
        rows = [dict(r) for r in result.mappings().all()]
    return {'query': keyword, 'count': len(rows), 'total': total, 'limit': limit, 'items': rows}


@app.post('/api/v1/requests', status_code=201)
async def create_request(payload: MaterialRequestCreate, user: dict = Depends(current_user)):
    if user['role'] not in {'USER','ADMIN'}:
        raise HTTPException(status_code=403, detail='Chỉ người lập yêu cầu được tạo yêu cầu mới')
    request_no = f"REQ-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
    async with engine.begin() as conn:
        result = await conn.execute(text('''INSERT INTO material_requests(request_no,requester_id,proposed_name,supplier_material_code,description,unit,material_group,status)
          VALUES(:no,:uid,:name,:supplier,:description,:unit,:grp,'PENDING_MASTERDATA') RETURNING id'''),
          {'no': request_no, 'uid': user['id'], 'name': payload.proposed_name.strip(), 'supplier': payload.supplier_material_code or None,
           'description': payload.description or None, 'unit': payload.unit or None, 'grp': payload.material_group or None})
        rid = result.scalar_one()
        await conn.execute(text("INSERT INTO request_history(request_id,actor_id,action,from_status,to_status,note) VALUES(:rid,:uid,'CREATE_REQUEST',NULL,'PENDING_MASTERDATA','Tạo yêu cầu đặt mã hàng')"), {'rid': rid, 'uid': user['id']})
        rr = await conn.execute(text(request_select_sql('WHERE r.id=:id')), {'id': rid})
        created = dict(rr.mappings().one())
    await notify_stage(created, 'CREATED')
    return created


@app.get('/api/v1/requests')
async def list_requests(status: str | None = Query(default=None), limit: int = Query(default=100, ge=1, le=300), user: dict = Depends(current_user)):
    conditions=[]; params={'limit':limit}
    if status: conditions.append('r.status=:status'); params['status']=status
    if user['role']=='USER': conditions.append('r.requester_id=:uid'); params['uid']=user['id']
    where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
    async with engine.connect() as conn:
        result=await conn.execute(text(request_select_sql(where)+' ORDER BY r.created_at DESC LIMIT :limit'),params)
        return {'items':[dict(r) for r in result.mappings().all()]}


@app.get('/api/v1/requests/{request_id}')
async def get_request(request_id:int,user:dict=Depends(current_user)):
    async with engine.connect() as conn:
        rr=await conn.execute(text(request_select_sql('WHERE r.id=:id')),{'id':request_id}); row=rr.mappings().one_or_none()
        if not row: raise HTTPException(status_code=404,detail='Không tìm thấy yêu cầu')
        if user['role']=='USER' and row['requester_id']!=user['id']: raise HTTPException(status_code=403,detail='Bạn không có quyền xem yêu cầu này')
        hr=await conn.execute(text('''SELECT h.id,h.action,h.from_status,h.to_status,h.note,h.created_at,u.full_name actor_name,u.email actor_email,u.role actor_role
          FROM request_history h LEFT JOIN users u ON u.id=h.actor_id WHERE h.request_id=:id ORDER BY h.created_at,h.id'''),{'id':request_id})
        return {'request':dict(row),'history':[dict(r) for r in hr.mappings().all()]}


@app.patch('/api/v1/requests/{request_id}')
async def edit_request(request_id:int,payload:MaterialRequestUpdate,user:dict=Depends(current_user)):
    async with engine.begin() as conn:
        cur=await conn.execute(text('SELECT * FROM material_requests WHERE id=:id FOR UPDATE'),{'id':request_id}); row=cur.mappings().one_or_none()
        if not row: raise HTTPException(status_code=404,detail='Không tìm thấy yêu cầu')
        if row['status']!='RETURNED_TO_REQUESTER': raise HTTPException(status_code=400,detail='Chỉ yêu cầu đã trả lại mới được sửa')
        if row['requester_id']!=user['id'] and user['role']!='ADMIN': raise HTTPException(status_code=403,detail='Chỉ người lập được sửa yêu cầu')
        await conn.execute(text('''UPDATE material_requests SET proposed_name=:name,supplier_material_code=:supplier,description=:description,unit=:unit,material_group=:grp,updated_at=NOW() WHERE id=:id'''),
          {'id':request_id,'name':payload.proposed_name.strip(),'supplier':payload.supplier_material_code or None,'description':payload.description or None,'unit':payload.unit or None,'grp':payload.material_group or None})
        await conn.execute(text("INSERT INTO request_history(request_id,actor_id,action,from_status,to_status,note) VALUES(:id,:uid,'EDIT_REQUEST','RETURNED_TO_REQUESTER','RETURNED_TO_REQUESTER','Người lập cập nhật lại toàn bộ thông tin yêu cầu')"),{'id':request_id,'uid':user['id']})
        rr=await conn.execute(text(request_select_sql('WHERE r.id=:id')),{'id':request_id}); updated=dict(rr.mappings().one())
    return updated


@app.post('/api/v1/requests/{request_id}/transition')
async def transition(request_id:int,payload:WorkflowTransition,user:dict=Depends(current_user)):
    action=payload.action.upper().strip()
    stage_to_notify = None
    async with engine.begin() as conn:
        cur=await conn.execute(text('SELECT * FROM material_requests WHERE id=:id FOR UPDATE'),{'id':request_id}); row=cur.mappings().one_or_none()
        if not row: raise HTTPException(status_code=404,detail='Không tìm thấy yêu cầu')
        state=row['status']; target=None; updates=['updated_at=NOW()']; params={'id':request_id}

        if action=='RETURN':
            expected='ACCOUNTING' if state=='PENDING_ACCOUNTING' else 'MASTERDATA'
            if state not in {'PENDING_MASTERDATA','PENDING_ACCOUNTING','PENDING_CODE_ASSIGNMENT'} or user['role']!=expected:
                raise HTTPException(status_code=403,detail='Bạn không có quyền trả lại ở bước này')
            if not payload.note or not payload.note.strip(): raise HTTPException(status_code=400,detail='Cần nhập lý do trả lại')
            target='RETURNED_TO_REQUESTER'; stage_to_notify='RETURNED'

        elif action=='RESUBMIT' and state=='RETURNED_TO_REQUESTER':
            if row['requester_id']!=user['id'] and user['role']!='ADMIN': raise HTTPException(status_code=403,detail='Chỉ người lập được gửi duyệt lại')
            target='PENDING_MASTERDATA'; stage_to_notify='RESUBMITTED'

        elif action=='APPROVE' and state=='PENDING_MASTERDATA':
            if user['role']!='MASTERDATA': raise HTTPException(status_code=403,detail='Chỉ Masterdata được duyệt bước này')
            if not payload.material_code or not payload.material_code.strip():
                raise HTTPException(status_code=400, detail='Masterdata cần nhập mã hàng mới trước khi chuyển Kế toán')
            target='PENDING_ACCOUNTING'
            updates.extend(['masterdata_note=:note','result_material_code=:code'])
            params['note']=payload.note; params['code']=payload.material_code.strip(); stage_to_notify='MASTERDATA_APPROVED'

        elif action=='ASSIGN_CODE' and state=='PENDING_CODE_ASSIGNMENT':
            if user['role']!='MASTERDATA': raise HTTPException(status_code=403,detail='Chỉ Masterdata được cấp mã')
            if not payload.material_code or not payload.material_code.strip(): raise HTTPException(status_code=400,detail='Cần nhập mã vật tư')
            target='PENDING_ACCOUNTING'
            updates.extend(['result_material_code=:code','masterdata_note=COALESCE(masterdata_note,:note)'])
            params['code']=payload.material_code.strip(); params['note']=payload.note; stage_to_notify='MASTERDATA_APPROVED'

        elif action=='APPROVE' and state=='PENDING_ACCOUNTING':
            if user['role']!='ACCOUNTING': raise HTTPException(status_code=403,detail='Chỉ Kế toán được duyệt bước này')
            if not row['result_material_code']:
                raise HTTPException(status_code=400,detail='Chưa có mã hàng mới. Vui lòng trả lại Masterdata.')
            target='COMPLETED'; updates.append('accounting_note=:note'); params['note']=payload.note; stage_to_notify='COMPLETED'

        else:
            raise HTTPException(status_code=400,detail=f'Thao tác {action} không hợp lệ ở trạng thái {state}')

        updates.append('status=:target'); params['target']=target
        await conn.execute(text(f"UPDATE material_requests SET {','.join(updates)} WHERE id=:id"),params)
        history_note = payload.note
        if state=='PENDING_MASTERDATA' and target=='PENDING_ACCOUNTING' and payload.material_code:
            history_note = f"{payload.note or ''}\nMã hàng mới: {payload.material_code.strip()}".strip()
        await conn.execute(text('INSERT INTO request_history(request_id,actor_id,action,from_status,to_status,note) VALUES(:id,:uid,:action,:from,:to,:note)'),
                           {'id':request_id,'uid':user['id'],'action':action,'from':state,'to':target,'note':history_note})
        rr=await conn.execute(text(request_select_sql('WHERE r.id=:id')),{'id':request_id}); updated=dict(rr.mappings().one())

    if stage_to_notify:
        await notify_stage(updated, stage_to_notify, payload.note)
    return updated


@app.get('/api/v1/admin/email-logs')
async def email_logs(limit: int = Query(default=100, ge=1, le=500), _: dict = Depends(require_role('ADMIN'))):
    async with engine.connect() as conn:
        result = await conn.execute(text('''SELECT id,request_id,recipient,subject,email_type,status,error_message,created_at
          FROM email_logs ORDER BY created_at DESC LIMIT :limit'''), {'limit': limit})
        return {'items': [dict(r) for r in result.mappings().all()]}
