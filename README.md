# Material Masterdata Portal

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
