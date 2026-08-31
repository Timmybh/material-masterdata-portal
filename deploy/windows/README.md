# Triển khai IIS + PostgreSQL trên Windows Server

Kiến trúc production không Docker:

- IIS phục vụ frontend tĩnh tại cổng `8088`.
- IIS URL Rewrite + ARR chuyển `/api` và `/health` về `127.0.0.1:8000`.
- FastAPI/Uvicorn chạy 4 worker dưới Windows Startup Task `MaterialMasterdataBackend`.
- Job import/hết hạn chạy riêng dưới Startup Task `MaterialMasterdataJobs`.
- Upload thủ công chỉ tạo job bền vững trong PostgreSQL rồi trả HTTP `202`; file chờ xử lý nằm tại `C:\Applications\MaterialMasterdataPortal\import-spool`.
- Cả hai Startup Task có `ExecutionTimeLimit = PT0S`; import không bị giới hạn bởi thời gian chờ của IIS/Uvicorn.
- PostgreSQL 18 chạy native dưới Windows Service của PostgreSQL.

## 1. Cài phần mềm nền

Trên Windows Server, cài:

1. PostgreSQL 18 x64 và pgAdmin 4.
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

Nếu PostgreSQL không nằm tại `C:\Program Files\PostgreSQL\18\bin`, truyền thêm `-PostgresBin`.

Script tạo database `masterdata`, extension `pg_trgm` và `unaccent`. Script deploy tạo/nâng cấp bảng một lần trước khi khởi động các web worker.

## 3. Triển khai lần đầu

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./deploy/windows/deploy-iis.ps1
```

Lần chạy đầu tạo file:

```text
C:\Applications\MaterialMasterdataPortal\backend\.env
```

Mở file này và thay tối thiểu:

```dotenv
DATABASE_URL=REPLACE_WITH_DATABASE_URL
JWT_SECRET=CHUOI_BI_MAT_DAI_NGAU_NHIEN
BOOTSTRAP_ADMIN_PASSWORD=MAT_KHAU_ADMIN_AN_TOAN
```

Nếu mật khẩu PostgreSQL chứa ký tự `@`, `:`, `/`, `#` hoặc `%`, phải URL-encode mật khẩu trong `DATABASE_URL`.

Chạy lại script:

```powershell
./deploy/windows/deploy-iis.ps1
```

Nếu Python không có trong `PATH`, truyền đường dẫn đầy đủ, ví dụ:

```powershell
./deploy/windows/deploy-iis.ps1 -PythonExe "D:\Program Files\Python312\python.exe"
```

Nếu máy chạy thêm ứng dụng khác đang dùng backend port `8000`, chọn port riêng,
ví dụ máy local dùng `8001`:

```powershell
./deploy/windows/deploy-iis.ps1 -BackendPort 8001
```

Script cập nhật đồng thời Uvicorn và IIS reverse proxy theo port này. Production
không truyền tham số vẫn dùng mặc định `8000`.

Truy cập: `http://localhost:8088`.

## 4. Import Danh mục vật tư

Đặt file mặc định tại:

```text
C:\MaterialMasterdataData\Danh muc vat tu.xlsx
```

Admin có thể đổi đường dẫn và giờ chạy tại màn hình **Quản trị**. Đường dẫn phải là đường dẫn nhìn thấy từ tài khoản chạy Startup Task.

Import thủ công và tự động dùng chung một hàng đợi. PostgreSQL chỉ cho phép một job ở trạng thái `queued`/`running`; advisory lock giữ suốt giao dịch thay thế dữ liệu nên nhiều web worker hoặc nhiều tiến trình job không thể chạy import trùng nhau. Nếu tiến trình job dừng giữa chừng, PostgreSQL rollback dữ liệu và lần khởi động sau đánh dấu job `failed`; job còn `queued` vẫn tiếp tục được xử lý.

Với file trên thư mục share/UNC, đổi tài khoản chạy task trong Task Scheduler sang tài khoản domain có quyền đọc thư mục share.

## 5. Nâng cấp source

Sau khi `git pull`, chạy lại:

```powershell
./deploy/windows/deploy-iis.ps1
```

Script dừng backend, cập nhật source/dependency, cập nhật Windows Startup Task, cập nhật frontend IIS và kiểm tra `/health`. File `.env` hiện tại được giữ nguyên.

## 6. Kiểm tra và vận hành

```powershell
Get-ScheduledTask -TaskName MaterialMasterdataBackend,MaterialMasterdataJobs
Get-ScheduledTask -TaskName MaterialMasterdataBackend,MaterialMasterdataJobs | Select-Object TaskName,@{N='ExecutionTimeLimit';E={$_.Settings.ExecutionTimeLimit}}
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8088/health
```

Log backend:

```text
C:\Applications\MaterialMasterdataPortal\backend\logs\backend.log
```

Khởi động lại backend:

```powershell
Stop-ScheduledTask MaterialMasterdataBackend
Start-ScheduledTask MaterialMasterdataBackend
Stop-ScheduledTask MaterialMasterdataJobs
Start-ScheduledTask MaterialMasterdataJobs
```

`/health` chỉ trả `ok` khi PostgreSQL thực sự kết nối được. Nếu giao diện chạy nhưng API lỗi `502`, kiểm tra hai Startup Task, log backend, kết nối PostgreSQL và `.env`.
