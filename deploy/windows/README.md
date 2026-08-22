# Triển khai IIS + SQL Server

## Thành phần bắt buộc

- Windows Server 2019 trở lên, IIS, URL Rewrite và Application Request Routing (ARR).
- SQL Server có cài tính năng **Full-Text and Semantic Extractions for Search**.
- Microsoft ODBC Driver 18 for SQL Server, Python 3.11+ và WinSW x64.

## Trình tự

1. Chạy `create-database.sql` bằng SSMS hoặc `sqlcmd`.
2. Chép WinSW x64 vào `C:\MaterialMasterdata\MaterialMasterdataBackend.exe`.
3. Chạy `install.ps1` bằng PowerShell Administrator.
4. Sửa `C:\MaterialMasterdata\.env`, đặc biệt `DATABASE_URL`, `JWT_SECRET` và tài khoản admin; chạy lại `install.ps1` để cập nhật service.
5. Trên IIS bật ARR Proxy và tạo site có Physical Path `C:\inetpub\wwwroot\material-masterdata`.

Backend chỉ nghe tại `127.0.0.1:8000`. IIS phục vụ frontend và chuyển `/api` đến backend. Worker để ở `1` nhằm bảo đảm lịch import 19:00 và lịch hủy yêu cầu không bị chạy lặp; khóa `sp_getapplock` tiếp tục bảo vệ tác vụ import.
