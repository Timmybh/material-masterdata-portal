# Triển khai IIS + PostgreSQL trên Windows Server

Kiến trúc production không Docker:

- IIS phục vụ frontend tĩnh tại cổng `8088`.
- IIS URL Rewrite + ARR chuyển `/api` và `/health` về `127.0.0.1:8000`.
- FastAPI/Uvicorn chạy dưới Windows Service `MaterialMasterdataBackend`.
- PostgreSQL 16 chạy native dưới Windows Service của PostgreSQL.

## 1. Cài phần mềm nền

Trên Windows Server, cài:

1. PostgreSQL 16 x64 và pgAdmin 4.
2. Python 3.12 x64; bật tùy chọn thêm Python vào `PATH`.
3. IIS URL Rewrite 2.1: <https://www.iis.net/downloads/microsoft/url-rewrite>
4. IIS Application Request Routing 3.0: <https://www.iis.net/downloads/microsoft/application-request-routing>

ARR phụ thuộc URL Rewrite, vì vậy cài URL Rewrite trước ARR. Script triển khai sẽ tự bật IIS và tính năng reverse proxy.

## 2. Chuẩn bị PostgreSQL

Mở PowerShell bằng **Run as Administrator** tại thư mục source:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./deploy/windows/install-postgresql.ps1 -DatabasePassword "MAT_KHAU_POSTGRES"
```

Nếu PostgreSQL không nằm tại `C:\Program Files\PostgreSQL\16\bin`, truyền thêm `-PostgresBin`.

Script tạo database `masterdata`, extension `pg_trgm` và `unaccent`. Backend tự tạo/nâng cấp bảng khi khởi động.

## 3. Triển khai lần đầu

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./deploy/windows/deploy-iis.ps1
```

Lần chạy đầu tạo file:

```text
C:\Apps\MaterialMasterdataPortal\backend\.env
```

Mở file này và thay tối thiểu:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:MAT_KHAU_POSTGRES@127.0.0.1:5432/masterdata
JWT_SECRET=CHUOI_BI_MAT_DAI_NGAU_NHIEN
BOOTSTRAP_ADMIN_PASSWORD=MAT_KHAU_ADMIN_AN_TOAN
```

Nếu mật khẩu PostgreSQL chứa ký tự `@`, `:`, `/`, `#` hoặc `%`, phải URL-encode mật khẩu trong `DATABASE_URL`.

Chạy lại script:

```powershell
./deploy/windows/deploy-iis.ps1
```

Truy cập: `http://localhost:8088`.

## 4. Import Danh mục vật tư

Đặt file mặc định tại:

```text
C:\MaterialMasterdataData\Danh muc vat tu.xlsx
```

Admin có thể đổi đường dẫn và giờ chạy tại màn hình **Quản trị**. Đường dẫn phải là đường dẫn nhìn thấy từ tài khoản chạy Windows Service.

Với file trên thư mục share/UNC, không dùng `LocalSystem`. Mở `services.msc` → `Material Masterdata Portal Backend` → **Log On** và đặt tài khoản domain có quyền đọc thư mục share.

## 5. Nâng cấp source

Sau khi `git pull`, chạy lại:

```powershell
./deploy/windows/deploy-iis.ps1
```

Script dừng backend, cập nhật source/dependency, cập nhật Windows Service, cập nhật frontend IIS và kiểm tra `/health`. File `.env` hiện tại được giữ nguyên.

## 6. Kiểm tra và vận hành

```powershell
Get-Service MaterialMasterdataBackend
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8088/health
```

Log backend:

```text
C:\Apps\MaterialMasterdataPortal\backend\logs\backend.log
```

Khởi động lại backend:

```powershell
Restart-Service MaterialMasterdataBackend
```

Nếu giao diện chạy nhưng API lỗi `502`, kiểm tra Windows Service, log backend, kết nối PostgreSQL và `.env`.
