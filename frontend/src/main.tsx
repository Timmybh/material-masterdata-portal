import React from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

function App() {
  return (
    <main className="page">
      <section className="hero">
        <span className="badge">Material Masterdata Portal V1.2</span>
        <h1>Tra cứu vật tư & tạo yêu cầu đặt mã hàng</h1>
        <p>Tìm vật tư hiện có trước khi gửi yêu cầu tạo mã mới.</p>
        <div className="search">
          <input placeholder="Nhập mã, tên hoặc mô tả vật tư..." />
          <button>Tìm kiếm</button>
        </div>
        <button className="request">+ Tạo yêu cầu đặt mã</button>
      </section>
      <section className="workflow">
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
