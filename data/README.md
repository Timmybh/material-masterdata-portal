# Dữ liệu khởi tạo

Copy file Excel gốc vào đúng đường dẫn:

`data/Danh muc vat tu.xlsx`

File này không được lưu trên GitHub. Trước khi chạy, nên lưu và đóng Excel để chắc chắn bản mới nhất đã được ghi xuống ổ đĩa. Chạy `scripts/reset-db-v1.5.1.ps1`; script sẽ kiểm tra file có đúng chữ ký XLSX rồi mới xóa database cũ.

Backend tự động thay thế 100% bảng `items` từ file này lúc 19:00 mỗi ngày theo múi giờ Việt Nam. Việc xóa và nhập lại chạy trong một transaction nên dữ liệu cũ vẫn được giữ nguyên nếu file hoặc quá trình import bị lỗi. Có thể đổi đường dẫn và lịch chạy bằng các biến `AUTO_IMPORT_*` trong `.env`.
