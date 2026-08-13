from .mailer import send_email

def request_details(req):
    return "\n".join([
        f"Mã yêu cầu: {req.id}", f"Tên vật tư: {req.item_name}", f"Đơn vị tính: {req.unit}",
        f"Loại vật tư: {req.item_type_name or '-'}", f"Nhóm hàng: {req.item_group or '-'}", f"Phân loại: {req.classification or '-'}",
        f"Nhóm cha: {req.parent_code or '-'}", f"Kind code: {req.kind_code or '-'}", f"Mã khách hàng: {req.customer_code or '-'}",
        f"Chi nhánh: {req.branch_code or '-'}", f"Quy cách: {req.specification or '-'}", f"Thông số kỹ thuật: {req.technical_specs or '-'}",
        f"Mục đích: {req.purpose or '-'}", f"Ghi chú: {req.notes or '-'}", f"Người tạo: {req.requester.name} <{req.requester.email}>",
        f"Thời gian gửi: {req.submitted_at:%d/%m/%Y %H:%M}"
    ])

def notify(to,subject,req,tail=""):
    body=request_details(req)+(f"\n\n{tail}" if tail else "")
    send_email(to,subject,body)
