# Material Masterdata Portal V1.6.10

## Kiến trúc triển khai hiện tại

Production được triển khai trực tiếp trên Windows Server, không dùng Docker:

- IIS phục vụ frontend và reverse proxy API tại cổng `8088`.
- FastAPI/Uvicorn chạy 4 worker bằng Windows Startup Task; job nền chạy trong task riêng.
- PostgreSQL 18 cài native, giữ PostgreSQL Full-Text Search và trigram search.
- Hướng dẫn và script: [`deploy/windows/README.md`](deploy/windows/README.md).

Các file Docker/Kubernetes cũ chỉ được giữ lại để tham khảo lịch sử, không thuộc luồng triển khai production hiện tại.

## Thay đổi V1.6.10

- Bộ phận không còn là trường bắt buộc khi tạo hoặc chỉnh sửa yêu cầu đặt mã.
- Mật khẩu người dùng tối thiểu 5 ký tự và được phép giống tên tài khoản.
- Kết quả tra cứu tiếp tục chỉ tải tối đa 20 dòng nhưng hiển thị đầy đủ tổng số kết quả phù hợp.

## Thay đổi V1.6.9

- Chuẩn bị tải khoảng 300 tài khoản tra cứu đồng thời bằng 4 Uvicorn worker.
- Tách scheduler/import khỏi web worker để không nhân bản job khi tăng worker.
- Giới hạn pool PostgreSQL theo worker, timeout nhanh và tự tái chế kết nối.
- `/health` kiểm tra PostgreSQL thật; bổ sung `/health/live` cho kiểm tra tiến trình.
- Scheduled Task chạy trực tiếp Python, không qua `cmd.exe`/batch launcher.
- Tự phục hồi trạng thái import bị gián đoạn và không chạy migration trong import giao diện.
- Ghi log đa tiến trình có xoay vòng; bổ sung index phục vụ đăng nhập và tra cứu mã.

## Thay đổi V1.6.8

- Admin có thể tải file `.xlsx`/`.csv` lên và import toàn bộ Danh mục vật tư ngay trên giao diện.
- Cấu hình job import tự động được lưu trong PostgreSQL: Kích hoạt/Dừng, giờ chạy và đường dẫn file.
- Màn hình Admin hiển thị job đang hoạt động, không hoạt động hoặc đang import; tự cập nhật trạng thái mỗi 5 giây.
- Lưu kết quả lần chạy gần nhất: nguồn chạy thủ công/tự động, thời gian, số dòng nhập/bỏ qua và lỗi gần nhất.
- Import thủ công và tự động dùng chung advisory lock và transaction; không thể chạy chồng nhau, lỗi sẽ rollback dữ liệu.

## Thay đổi V1.6

- Dò mặt hàng trùng bằng PostgreSQL tại màn hình Người lập, Masterdata và Kế toán; so sánh tên, tính chất/quy cách và mục đích sử dụng, không gọi AI.
- AI chỉ đề xuất **tên mặt hàng** chuẩn dựa trên thông tin người dùng đã nhập; không tự thêm chủng loại hoặc nhãn hiệu.
- Thêm trường chỉ đọc `Mã vật tư mới cấp` ở cuối yêu cầu.
- Kế toán nhập `Ghi chú Kế toán` và `Mã mới`; khi duyệt, mã được cập nhật vào yêu cầu của người lập.
- Cảnh báo kiểm tra trùng nhấp nháy nhẹ để thu hút sự chú ý.
- OpenAI API key chỉ cấu hình trong backend qua `OPENAI_API_KEY`, tuyệt đối không nhập vào giao diện hoặc commit lên Git.
- Đăng nhập nội bộ bằng email hoặc tên tài khoản và mật khẩu. Mật khẩu được băm PBKDF2-SHA256, không lưu dạng rõ.
- Trước lần chạy đầu, đặt `BOOTSTRAP_ADMIN_EMAILS`, `BOOTSTRAP_ADMIN_USERNAME` và `BOOTSTRAP_ADMIN_PASSWORD` trong `.env`; phải đổi mật khẩu mẫu.

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
- V1.5.2 khôi phục chức năng Admin tạo người dùng mới và mở rộng Full Text Search theo từng từ khóa, không dấu, mã cũ/mới và chuỗi gần đúng.

## Triển khai Docker cũ (chỉ lưu tham khảo)

Phần này không còn thuộc phương án triển khai hiện tại. Production sử dụng hướng dẫn IIS + PostgreSQL native ở đầu tài liệu.

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

Truy cập `http://localhost:8088`. PostgreSQL mặc định: `localhost:5432`, database `masterdata`, user `postgres`; mật khẩu phải được đặt riêng trong `.env` và không commit vào Git.

Service `db-init` tự tạo/nâng cấp schema và thay thế toàn bộ danh mục từ `data/Danh muc vat tu.xlsx`. File dữ liệu lớn không lưu trong Git để tránh hỏng file nhị phân khi clone; hãy copy file Excel gốc vào thư mục `data` trước khi chạy reset. Script sẽ kiểm tra chữ ký XLSX trước khi thay thế dữ liệu.

Backend cũng tự động thay thế 100% danh mục từ file Excel mỗi ngày lúc 19:00 theo giờ Việt Nam. Hệ thống kiểm tra toàn bộ file trước, sau đó xóa và nhập lại bảng `items` trong cùng một transaction; nếu import lỗi, dữ liệu cũ được rollback và giữ nguyên. Các giá trị trong `.env` là mặc định cho lần khởi tạo đầu tiên; sau đó Admin cấu hình trực tiếp trên giao diện:

```dotenv
AUTO_IMPORT_ENABLED=true
AUTO_IMPORT_FILE_PATH=/data/Danh muc vat tu.xlsx
AUTO_IMPORT_HOUR=19
AUTO_IMPORT_MINUTE=0
AUTO_IMPORT_TIMEZONE=Asia/Ho_Chi_Minh
```

Khi chạy Docker, đặt file ở `data/Danh muc vat tu.xlsx`; thư mục `data` đã được mount chỉ đọc vào `/data` trong container backend.

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
- `GET/PUT /api/admin/item-import/config`: xem và lưu cấu hình job import.
- `POST /api/admin/item-import/upload`: import thủ công Danh mục vật tư.

## Nâng cấp từ database cũ

Backend chạy migration idempotent khi khởi động, sau đó `db-init` thay thế toàn bộ danh mục. Dữ liệu yêu cầu và người dùng hiện có được giữ nguyên.

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

## Kubernetes cũ (chỉ lưu tham khảo)

```powershell
Copy-Item ./k8s/secret.example.yaml ./k8s/secret.yaml
./scripts/build-images.ps1
./scripts/deploy-k8s.ps1
./scripts/import-seed.ps1
```

Khi triển khai production, đổi mật khẩu mặc định, JWT secret, cấu hình Google OAuth/SMTP, TLS, backup PostgreSQL và Secret management.
