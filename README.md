# Material Masterdata Portal V1.5.1

Ứng dụng tra cứu danh mục vật tư BRAVO và workflow yêu cầu tạo mã mới cho DOVITEC.

## Thay đổi V1.5

- Tái cấu trúc bảng `items` theo `data/Danh muc vat tu.xlsx`: 22.806 dòng, 35 cột nguồn, 5 loại vật tư, 23 nhóm hàng và cây `ParentId`/`ParentCode`.
- Lưu đầy đủ mã cũ/mới, tên phụ, loại, nhóm, phân loại, khách hàng, chi nhánh, thông tin giá thành, giá, các cờ màu/size/art và audit nguồn.
- Ánh xạ 1–1 đủ 35 cột Excel. Hai cột nguồn không có tên được lưu tại `source_extra_1`, `source_extra_2`; `_SelectKey__cumontli` được lưu tại `source_select_key`.
- Migration tự kiểm tra danh sách cột sau khi chạy và dừng với lỗi rõ ràng nếu schema PostgreSQL còn thiếu.
- Tìm kiếm PostgreSQL FTS + trigram trên toàn bộ trường nhận diện; API trả tổng số kết quả và giao diện hiển thị `20/tổng số`.
- Luồng trả lại hoàn chỉnh: Masterdata trả người lập → người lập sửa → gửi duyệt lại.
- Nút **Hủy** trong màn hình duyệt không gọi API và không thay đổi trạng thái.
- Email tại từng bước chứa tên vật tư, ĐVT, thời gian gửi, người tạo và đầy đủ thông tin phân loại.
- Email workflow hiện được tạm ngưng bằng `EMAIL_NOTIFICATIONS_ENABLED=false`. Đổi thành `true` khi cần bật lại.
- Quản trị tài khoản, role và trạng thái hoạt động.

## Chạy bằng Docker Desktop

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

Truy cập `http://localhost:8080`. PostgreSQL mặc định: `localhost:5432`, database `masterdata`, user `postgres`, password `12345678`.

Service `db-init` tự tạo/nâng cấp schema và upsert dữ liệu từ `data/Danh muc vat tu.xlsx`. Import có thể chạy lại an toàn:

```powershell
./scripts/init-db-and-data.ps1
```

## API chính

- `GET /api/items/search?q=...&limit=20`: trả `{items,total,limit,query}`.
- `GET /api/items/{id}`: chi tiết đầy đủ vật tư.
- `POST /api/requests`: tạo yêu cầu.
- `PATCH /api/requests/{id}` và `POST /api/requests/{id}/resubmit`: sửa/gửi lại yêu cầu bị trả.
- `/api/masterdata/*`, `/api/accounting/*`: duyệt và trả kết quả.
- `/api/admin/users`: quản lý tài khoản và role.

## Nâng cấp từ database cũ

Backend chạy migration idempotent khi khởi động, sau đó `db-init` upsert lại toàn bộ danh mục. Dữ liệu yêu cầu và người dùng hiện có được giữ nguyên.

### Làm mới hoàn toàn database (khuyến nghị cho V1.5.1)

Lệnh dưới đây xóa volume PostgreSQL hiện tại, bao gồm user, yêu cầu và dữ liệu test; sau đó tạo schema mới và import lại 22.806 dòng danh mục:

```powershell
./scripts/reset-db-v1.5.1.ps1
```

Nhập `RESET` khi được hỏi xác nhận. Không dùng lệnh này nếu cần giữ dữ liệu đang vận hành.

Kiểm tra số cột và số dòng sau khi import:

```powershell
docker compose exec postgres psql -U postgres -d masterdata -c "SELECT COUNT(*) AS column_count FROM information_schema.columns WHERE table_schema='public' AND table_name='items';"
docker compose exec postgres psql -U postgres -d masterdata -c "SELECT COUNT(*) AS material_count FROM items;"
```

## Kubernetes

```powershell
Copy-Item ./k8s/secret.example.yaml ./k8s/secret.yaml
./scripts/build-images.ps1
./scripts/deploy-k8s.ps1
./scripts/import-seed.ps1
```

Khi triển khai production, đổi mật khẩu mặc định, JWT secret, cấu hình Google OAuth/SMTP, TLS, backup PostgreSQL và Secret management.
