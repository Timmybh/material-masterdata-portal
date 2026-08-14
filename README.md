# Material Masterdata Portal

## V1.5.2

- Bổ sung bảng `categories`, `brands` và khóa ngoại `materials.category_id`, `materials.brand_id`.
- Dữ liệu khởi tạo gồm nhóm thiết bị CNTT, máy móc/phụ tùng nhà máy may và các nhãn hiệu phổ biến.
- Tra cứu vật tư hiển thị, tìm kiếm theo Chủng loại và Nhãn hiệu.
- Form tạo yêu cầu cho phép chọn Chủng loại/Nhãn hiệu và dùng AI đề xuất tên chuẩn, đồng thời cảnh báo vật tư gần trùng.
- AI chỉ đề xuất; người dùng phải xác nhận. Khi chưa cấu hình `OPENAI_API_KEY`, hệ thống dùng quy tắc nội bộ.

Dự án tạo yêu cầu đặt mã hàng.

## Mục tiêu
- Tra cứu vật tư bằng PostgreSQL Full Text Search.
- Đăng nhập bằng Google SSO.
- Tạo yêu cầu đặt mã hàng.
- Workflow duyệt: Người dùng → Nhân sự phụ trách Masterdata → Kế toán → trả kết quả.
- Backend FastAPI, frontend React/Vite.
- Hỗ trợ Docker và Kubernetes.

## Cấu trúc dự kiến

```text
frontend/   React + Vite
backend/    FastAPI
 database/  PostgreSQL schema + seed data
k8s/        Kubernetes manifests
```

## PostgreSQL local
- Host: localhost
- Port: 5432

> Không sử dụng mật khẩu dev mặc định cho môi trường production.
