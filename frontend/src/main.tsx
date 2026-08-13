import React, { FormEvent, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API_URL = 'http://localhost:8000';

type Material = {
  id: number;
  material_code: string;
  material_name: string;
  description?: string;
  unit?: string;
  material_group?: string;
};

type RequestForm = {
  proposed_name: string;
  description: string;
  unit: string;
  material_group: string;
};

const emptyRequest: RequestForm = {
  proposed_name: '',
  description: '',
  unit: '',
  material_group: '',
};

function App() {
  const [query, setQuery] = useState('');
  const [materials, setMaterials] = useState<Material[]>([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showRequest, setShowRequest] = useState(false);
  const [requestForm, setRequestForm] = useState<RequestForm>(emptyRequest);
  const [requestMessage, setRequestMessage] = useState('');
  const [saving, setSaving] = useState(false);

  async function searchMaterials(event?: FormEvent) {
    event?.preventDefault();
    setLoading(true);
    setError('');
    setRequestMessage('');

    try {
      const response = await fetch(
        `${API_URL}/api/v1/materials/search?q=${encodeURIComponent(query)}`,
      );
      if (!response.ok) throw new Error('Không thể tra cứu vật tư.');
      const data = await response.json();
      setMaterials(data.items ?? []);
      setSearched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Có lỗi xảy ra.');
    } finally {
      setLoading(false);
    }
  }

  async function createRequest(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError('');
    setRequestMessage('');

    try {
      const response = await fetch(`${API_URL}/api/v1/requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestForm),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Không thể tạo yêu cầu.');
      }

      setRequestMessage(
        `Đã tạo yêu cầu ${data.request_no}. Trạng thái: ${data.status}.`,
      );
      setRequestForm(emptyRequest);
      setShowRequest(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Có lỗi xảy ra.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <span className="badge">Material Masterdata Portal V1.3</span>
        <h1>Tra cứu vật tư & tạo yêu cầu đặt mã hàng</h1>
        <p>Tìm vật tư hiện có trước khi gửi yêu cầu tạo mã mới.</p>

        <form className="search" onSubmit={searchMaterials}>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Nhập mã, tên hoặc mô tả vật tư..."
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Đang tìm...' : 'Tìm kiếm'}
          </button>
        </form>

        <button
          className="request"
          type="button"
          onClick={() => setShowRequest((value) => !value)}
        >
          {showRequest ? 'Đóng form' : '+ Tạo yêu cầu đặt mã'}
        </button>

        {error && <div className="notice error">{error}</div>}
        {requestMessage && <div className="notice success">{requestMessage}</div>}
      </section>

      {searched && (
        <section className="results">
          <div className="section-title">
            <div>
              <span className="eyebrow">KẾT QUẢ TRA CỨU</span>
              <h2>{materials.length} vật tư được tìm thấy</h2>
            </div>
          </div>

          {materials.length === 0 ? (
            <div className="empty">
              Không tìm thấy vật tư phù hợp. Anh có thể tạo yêu cầu đặt mã mới.
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Mã vật tư</th>
                    <th>Tên vật tư</th>
                    <th>Mô tả</th>
                    <th>ĐVT</th>
                    <th>Nhóm</th>
                  </tr>
                </thead>
                <tbody>
                  {materials.map((material) => (
                    <tr key={material.id}>
                      <td><strong>{material.material_code}</strong></td>
                      <td>{material.material_name}</td>
                      <td>{material.description || '-'}</td>
                      <td>{material.unit || '-'}</td>
                      <td>{material.material_group || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {showRequest && (
        <section className="request-panel">
          <span className="eyebrow">YÊU CẦU MỚI</span>
          <h2>Tạo yêu cầu đặt mã hàng</h2>
          <p>Yêu cầu sau khi tạo sẽ chuyển đến Nhân sự phụ trách Masterdata.</p>

          <form className="request-form" onSubmit={createRequest}>
            <label>
              Tên vật tư đề xuất *
              <input
                required
                minLength={2}
                value={requestForm.proposed_name}
                onChange={(event) =>
                  setRequestForm({ ...requestForm, proposed_name: event.target.value })
                }
                placeholder="Ví dụ: Vải cotton 100% màu trắng"
              />
            </label>
            <label>
              Mô tả
              <textarea
                value={requestForm.description}
                onChange={(event) =>
                  setRequestForm({ ...requestForm, description: event.target.value })
                }
                placeholder="Thông số, quy cách, mục đích sử dụng..."
              />
            </label>
            <div className="form-row">
              <label>
                Đơn vị tính
                <input
                  value={requestForm.unit}
                  onChange={(event) =>
                    setRequestForm({ ...requestForm, unit: event.target.value })
                  }
                  placeholder="PCS, KG, M..."
                />
              </label>
              <label>
                Nhóm vật tư
                <input
                  value={requestForm.material_group}
                  onChange={(event) =>
                    setRequestForm({ ...requestForm, material_group: event.target.value })
                  }
                  placeholder="GENERAL..."
                />
              </label>
            </div>
            <button className="primary" type="submit" disabled={saving}>
              {saving ? 'Đang gửi...' : 'Gửi yêu cầu'}
            </button>
          </form>
        </section>
      )}

      <section className="workflow">
        <span className="eyebrow">WORKFLOW</span>
        <h2>Quy trình phê duyệt</h2>
        <div className="steps">
          <div>1. Người dùng</div><b>→</b>
          <div>2. Nhân sự phụ trách Masterdata</div><b>→</b>
          <div>3. Kế toán</div><b>→</b>
          <div>4. Trả kết quả</div>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
