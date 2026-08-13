import React, { FormEvent, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API_URL = '';
const DEMO_REQUESTER_EMAIL = 'user@example.com';

type Material = { id:number; material_code:string; material_name:string; description?:string; unit?:string; material_group?:string };
type MaterialRequest = { id:number; request_no:string; requester_email?:string; requester_name?:string; proposed_name:string; description?:string; unit?:string; material_group?:string; status:string; masterdata_note?:string; accounting_note?:string; result_material_code?:string; created_at:string; updated_at:string };
type HistoryItem = { id:number; action:string; from_status?:string; to_status?:string; note?:string; created_at:string; actor_name?:string; actor_email?:string; actor_role?:string };
type RequestForm = { proposed_name:string; description:string; unit:string; material_group:string };

const emptyRequest: RequestForm = { proposed_name:'', description:'', unit:'', material_group:'' };
const statusLabels: Record<string,string> = {
  PENDING_MASTERDATA:'Chờ Masterdata duyệt',
  PENDING_ACCOUNTING:'Chờ Kế toán duyệt',
  PENDING_CODE_ASSIGNMENT:'Chờ Masterdata cấp mã',
  RETURNED_TO_REQUESTER:'Đã trả lại người lập',
  COMPLETED:'Hoàn tất',
  REJECTED:'Từ chối',
};

function formatDate(value?:string) {
  if (!value) return '-';
  return new Intl.DateTimeFormat('vi-VN',{dateStyle:'short',timeStyle:'medium'}).format(new Date(value));
}

function App() {
  const [query,setQuery] = useState('');
  const [materials,setMaterials] = useState<Material[]>([]);
  const [searched,setSearched] = useState(false);
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState('');
  const [showRequest,setShowRequest] = useState(false);
  const [requestForm,setRequestForm] = useState<RequestForm>(emptyRequest);
  const [createdRequest,setCreatedRequest] = useState<MaterialRequest|null>(null);
  const [saving,setSaving] = useState(false);
  const [requests,setRequests] = useState<MaterialRequest[]>([]);
  const [requestsLoading,setRequestsLoading] = useState(false);
  const [statusFilter,setStatusFilter] = useState('');
  const [selectedRequest,setSelectedRequest] = useState<MaterialRequest|null>(null);
  const [history,setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading,setHistoryLoading] = useState(false);
  const [editingRequest,setEditingRequest] = useState<MaterialRequest|null>(null);
  const [editForm,setEditForm] = useState<RequestForm>(emptyRequest);
  const [editSaving,setEditSaving] = useState(false);

  async function loadRequests(status=statusFilter) {
    setRequestsLoading(true); setError('');
    try {
      const suffix = status ? `?status=${encodeURIComponent(status)}` : '';
      const r = await fetch(`${API_URL}/api/v1/requests${suffix}`);
      if (!r.ok) throw new Error('Không thể tải danh sách yêu cầu.');
      const data = await r.json(); setRequests(data.items ?? []);
    } catch(e) { setError(e instanceof Error ? e.message : 'Có lỗi xảy ra.'); }
    finally { setRequestsLoading(false); }
  }

  useEffect(()=>{ loadRequests(''); },[]);

  async function searchMaterials(event?:FormEvent) {
    event?.preventDefault(); setLoading(true); setError(''); setCreatedRequest(null);
    try {
      const r = await fetch(`${API_URL}/api/v1/materials/search?q=${encodeURIComponent(query)}`);
      if (!r.ok) throw new Error('Không thể tra cứu vật tư.');
      const data = await r.json(); setMaterials(data.items ?? []); setSearched(true);
    } catch(e) { setError(e instanceof Error ? e.message : 'Có lỗi xảy ra.'); }
    finally { setLoading(false); }
  }

  async function createRequest(event:FormEvent) {
    event.preventDefault(); setSaving(true); setError(''); setCreatedRequest(null);
    try {
      const r = await fetch(`${API_URL}/api/v1/requests`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...requestForm,requester_email:DEMO_REQUESTER_EMAIL})});
      const data = await r.json(); if (!r.ok) throw new Error(data.detail || 'Không thể tạo yêu cầu.');
      setCreatedRequest(data); setRequestForm(emptyRequest); setShowRequest(false); await loadRequests('');
    } catch(e) { setError(e instanceof Error ? e.message : 'Có lỗi xảy ra.'); }
    finally { setSaving(false); }
  }

  async function openHistory(request:MaterialRequest) {
    setSelectedRequest(request); setHistoryLoading(true); setHistory([]);
    try {
      const r = await fetch(`${API_URL}/api/v1/requests/${request.id}`); const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Không thể tải lịch sử yêu cầu.');
      setSelectedRequest(data.request); setHistory(data.history ?? []);
    } catch(e) { setError(e instanceof Error ? e.message : 'Có lỗi xảy ra.'); }
    finally { setHistoryLoading(false); }
  }

  async function transitionRequest(request:MaterialRequest, action:'APPROVE'|'RETURN'|'REJECT'|'ASSIGN_CODE'|'RESUBMIT') {
    let actorEmail='masterdata@example.com', note='', materialCode='';
    if (request.status==='PENDING_ACCOUNTING') actorEmail='accounting@example.com';
    if (action==='RESUBMIT') actorEmail=request.requester_email || DEMO_REQUESTER_EMAIL;
    if (action==='RETURN') {
      const entered=window.prompt('Nhập lý do trả lại người lập:'); if (entered===null) return;
      note=entered.trim(); if (!note) { setError('Cần nhập lý do trả lại người lập.'); return; }
    } else if (action==='APPROVE') {
      const entered=window.prompt('Ghi chú duyệt (có thể để trống):'); if (entered===null) return; note=entered;
    } else if (action==='ASSIGN_CODE') {
      const code=window.prompt('Nhập mã vật tư được cấp:'); if (code===null) return; materialCode=code.trim(); if (!materialCode) return;
      const entered=window.prompt('Ghi chú cấp mã (có thể để trống):'); if (entered===null) return; note=entered;
    } else if (action==='RESUBMIT') {
      if (!window.confirm('Gửi lại yêu cầu này cho Masterdata duyệt từ đầu?')) return;
      note='Người lập gửi duyệt lại sau khi cập nhật';
    } else if (action==='REJECT') {
      const entered=window.prompt('Nhập lý do từ chối:'); if (entered===null) return; note=entered.trim(); if (!note) return;
    }
    setError('');
    try {
      const r=await fetch(`${API_URL}/api/v1/requests/${request.id}/transition`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,actor_email:actorEmail,note:note||null,material_code:materialCode||null})});
      const data=await r.json(); if (!r.ok) throw new Error(data.detail || 'Không thể xử lý yêu cầu.');
      await loadRequests(statusFilter); if (selectedRequest?.id===request.id) await openHistory(data);
    } catch(e) { setError(e instanceof Error ? e.message : 'Có lỗi xảy ra.'); }
  }

  function openEditRequest(request:MaterialRequest) {
    setEditingRequest(request);
    setEditForm({proposed_name:request.proposed_name,description:request.description||'',unit:request.unit||'',material_group:request.material_group||''});
  }

  async function saveEditedRequest(event:FormEvent, resubmit:boolean) {
    event.preventDefault(); if (!editingRequest) return; setEditSaving(true); setError('');
    try {
      const r=await fetch(`${API_URL}/api/v1/requests/${editingRequest.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({...editForm,editor_email:editingRequest.requester_email||DEMO_REQUESTER_EMAIL})});
      const updated=await r.json(); if (!r.ok) throw new Error(updated.detail || 'Không thể cập nhật yêu cầu.');
      setEditingRequest(null); await loadRequests(statusFilter);
      if (resubmit) await transitionRequest(updated,'RESUBMIT');
    } catch(e) { setError(e instanceof Error ? e.message : 'Có lỗi xảy ra.'); }
    finally { setEditSaving(false); }
  }

  function renderActions(request:MaterialRequest) {
    if (request.status==='PENDING_MASTERDATA') return <div className="actions"><button className="small approve" onClick={()=>transitionRequest(request,'APPROVE')}>Masterdata duyệt</button><button className="small reject" onClick={()=>transitionRequest(request,'RETURN')}>Trả lại người lập</button></div>;
    if (request.status==='PENDING_ACCOUNTING') return <div className="actions"><button className="small approve" onClick={()=>transitionRequest(request,'APPROVE')}>Kế toán duyệt</button><button className="small reject" onClick={()=>transitionRequest(request,'RETURN')}>Trả lại người lập</button></div>;
    if (request.status==='PENDING_CODE_ASSIGNMENT') return <div className="actions"><button className="small approve" onClick={()=>transitionRequest(request,'ASSIGN_CODE')}>Cấp mã vật tư</button><button className="small reject" onClick={()=>transitionRequest(request,'RETURN')}>Trả lại người lập</button></div>;
    if (request.status==='RETURNED_TO_REQUESTER') return <div className="actions"><button className="small approve" onClick={()=>openEditRequest(request)}>Mở & sửa yêu cầu</button><button className="small" onClick={()=>transitionRequest(request,'RESUBMIT')}>Gửi duyệt lại</button></div>;
    return null;
  }

  return <main className="page">
    <section className="hero">
      <span className="badge">Material Masterdata Portal V1.4.2</span>
      <h1>Tra cứu vật tư & tạo yêu cầu đặt mã hàng</h1>
      <p>Tra cứu trước khi tạo mã mới và theo dõi toàn bộ quy trình phê duyệt.</p>
      <form className="search" onSubmit={searchMaterials}><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Nhập mã, tên hoặc mô tả vật tư..."/><button disabled={loading}>{loading?'Đang tìm...':'Tìm kiếm'}</button></form>
      <button className="request" type="button" onClick={()=>setShowRequest(v=>!v)}>{showRequest?'Đóng form':'+ Tạo yêu cầu đặt mã'}</button>
      {error&&<div className="notice error">{error}</div>}
      {createdRequest&&<div className="created-card"><div className="created-head"><div><span className="created-label">TẠO YÊU CẦU THÀNH CÔNG</span><strong>{createdRequest.request_no}</strong></div><span className={`status ${createdRequest.status.toLowerCase()}`}>{statusLabels[createdRequest.status]||createdRequest.status}</span></div><div className="created-grid"><div><span>Tên vật tư</span><b>{createdRequest.proposed_name}</b></div><div><span>Đơn vị tính</span><b>{createdRequest.unit||'-'}</b></div><div><span>Người tạo yêu cầu</span><b>{createdRequest.requester_name||createdRequest.requester_email||'-'}</b></div><div><span>Thời gian tạo</span><b>{formatDate(createdRequest.created_at)}</b></div></div></div>}
    </section>

    {showRequest&&<section className="request-panel"><span className="eyebrow">YÊU CẦU MỚI</span><h2>Tạo yêu cầu đặt mã hàng</h2><p>Yêu cầu sau khi tạo sẽ chuyển đến Nhân sự phụ trách Masterdata.</p><form className="request-form" onSubmit={createRequest}><label>Tên vật tư đề xuất *<input required minLength={2} value={requestForm.proposed_name} onChange={e=>setRequestForm({...requestForm,proposed_name:e.target.value})}/></label><label>Mô tả<textarea value={requestForm.description} onChange={e=>setRequestForm({...requestForm,description:e.target.value})}/></label><div className="form-row"><label>Đơn vị tính<input value={requestForm.unit} onChange={e=>setRequestForm({...requestForm,unit:e.target.value})}/></label><label>Nhóm vật tư<input value={requestForm.material_group} onChange={e=>setRequestForm({...requestForm,material_group:e.target.value})}/></label></div><button className="primary" disabled={saving}>{saving?'Đang gửi...':'Gửi yêu cầu'}</button></form></section>}

    {searched&&<section className="results"><span className="eyebrow">KẾT QUẢ TRA CỨU</span><h2>{materials.length} vật tư được tìm thấy</h2>{materials.length===0?<div className="empty">Không tìm thấy vật tư phù hợp.</div>:<div className="table-wrap"><table><thead><tr><th>Mã vật tư</th><th>Tên vật tư</th><th>Mô tả</th><th>ĐVT</th><th>Nhóm</th></tr></thead><tbody>{materials.map(m=><tr key={m.id}><td><strong>{m.material_code}</strong></td><td>{m.material_name}</td><td>{m.description||'-'}</td><td>{m.unit||'-'}</td><td>{m.material_group||'-'}</td></tr>)}</tbody></table></div>}</section>}

    <section className="requests-section"><div className="section-title"><div><span className="eyebrow">QUẢN LÝ YÊU CẦU</span><h2>Danh sách yêu cầu đặt mã</h2></div><button className="refresh" onClick={()=>loadRequests(statusFilter)} disabled={requestsLoading}>{requestsLoading?'Đang tải...':'↻ Làm mới'}</button></div><div className="filters">{[['','Tất cả'],['PENDING_MASTERDATA','Chờ Masterdata'],['PENDING_ACCOUNTING','Chờ Kế toán'],['PENDING_CODE_ASSIGNMENT','Chờ cấp mã'],['RETURNED_TO_REQUESTER','Trả lại người lập'],['COMPLETED','Hoàn tất'],['REJECTED','Từ chối']].map(([v,l])=><button key={v||'all'} className={statusFilter===v?'active':''} onClick={()=>{setStatusFilter(v);loadRequests(v)}}>{l}</button>)}</div><div className="request-list">{requests.map(r=><article className="request-card" key={r.id}><div className="request-card-main"><div className="request-no">{r.request_no}</div><h3>{r.proposed_name}</h3><div className="meta"><span>ĐVT: <b>{r.unit||'-'}</b></span><span>Người tạo: <b>{r.requester_name||r.requester_email||'-'}</b></span><span>Tạo lúc: <b>{formatDate(r.created_at)}</b></span>{r.result_material_code&&<span>Mã được cấp: <b>{r.result_material_code}</b></span>}</div></div><div className="request-card-side"><span className={`status ${r.status.toLowerCase()}`}>{statusLabels[r.status]||r.status}</span>{renderActions(r)}<button className="history-btn" onClick={()=>openHistory(r)}>Xem lịch sử</button></div></article>)}{!requestsLoading&&requests.length===0&&<div className="empty">Không có yêu cầu phù hợp bộ lọc.</div>}</div></section>

    <section className="workflow"><span className="eyebrow">WORKFLOW V1.4.2</span><h2>Quy trình phê duyệt</h2><div className="steps"><div>1. Người dùng tạo / gửi lại</div><b>→</b><div>2. Masterdata duyệt hoặc trả lại</div><b>→</b><div>3. Kế toán duyệt hoặc trả lại</div><b>→</b><div>4. Masterdata cấp mã</div><b>→</b><div>5. Hoàn tất</div></div></section>

    {editingRequest&&<div className="modal-backdrop" onClick={()=>setEditingRequest(null)}><div className="modal edit-modal" onClick={e=>e.stopPropagation()}><button className="close" onClick={()=>setEditingRequest(null)}>×</button><span className="eyebrow">SỬA YÊU CẦU ĐÃ TRẢ LẠI</span><h2>{editingRequest.request_no}</h2><p>Mở lại toàn bộ nội dung yêu cầu để người lập chỉnh sửa trước khi gửi duyệt lại.</p><form className="edit-form" onSubmit={e=>saveEditedRequest(e,false)}><label>Tên vật tư đề xuất *<input required minLength={2} value={editForm.proposed_name} onChange={e=>setEditForm({...editForm,proposed_name:e.target.value})}/></label><label>Mô tả<textarea value={editForm.description} onChange={e=>setEditForm({...editForm,description:e.target.value})}/></label><div className="form-row"><label>Đơn vị tính<input value={editForm.unit} onChange={e=>setEditForm({...editForm,unit:e.target.value})}/></label><label>Nhóm vật tư<input value={editForm.material_group} onChange={e=>setEditForm({...editForm,material_group:e.target.value})}/></label></div><div className="modal-actions"><button className="secondary" type="submit" disabled={editSaving}>{editSaving?'Đang lưu...':'Lưu thay đổi'}</button><button className="primary" type="button" disabled={editSaving} onClick={e=>saveEditedRequest(e as unknown as FormEvent,true)}>Lưu & gửi duyệt lại</button></div></form></div></div>}

    {selectedRequest&&<div className="modal-backdrop" onClick={()=>setSelectedRequest(null)}><div className="modal" onClick={e=>e.stopPropagation()}><button className="close" onClick={()=>setSelectedRequest(null)}>×</button><span className="eyebrow">LỊCH SỬ YÊU CẦU</span><h2>{selectedRequest.request_no}</h2><h3>{selectedRequest.proposed_name}</h3>{historyLoading?<p>Đang tải...</p>:<div className="timeline">{history.map(h=><div className="timeline-item" key={h.id}><div className="dot"/><div><b>{h.action}</b><p>{h.actor_name||h.actor_email||'Hệ thống'} · {formatDate(h.created_at)}</p><p>{h.from_status?`${statusLabels[h.from_status]||h.from_status} → `:''}{statusLabels[h.to_status||'']||h.to_status}</p>{h.note&&<blockquote>{h.note}</blockquote>}</div></div>)}</div>}</div></div>}
  </main>;
}

createRoot(document.getElementById('root')!).render(<App/>);
