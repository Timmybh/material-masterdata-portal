-- Auto-seed for newly initialized PostgreSQL volumes.
-- Same dataset as database/seed/seed_v1_4_2.sql.

INSERT INTO users (email, full_name, role, is_active) VALUES
('user@example.com', 'Nguyễn Văn Người Dùng', 'USER', TRUE),
('user2@example.com', 'Trần Minh Anh', 'USER', TRUE),
('masterdata@example.com', 'Lê Thanh Masterdata', 'MASTERDATA', TRUE),
('accounting@example.com', 'Phạm Ngọc Kế Toán', 'ACCOUNTING', TRUE)
ON CONFLICT (email) DO UPDATE SET
    full_name = EXCLUDED.full_name,
    role = EXCLUDED.role,
    is_active = EXCLUDED.is_active;

INSERT INTO materials (material_code, material_name, description, unit, material_group) VALUES
('VT000001', 'Vải cotton 100% trắng', 'Vải cotton dệt thoi màu trắng dùng cho sản xuất', 'M', 'FABRIC'),
('VT000002', 'Vải polyester 65/35 xanh navy', 'Vải polyester cotton pha 65/35 màu xanh navy', 'M', 'FABRIC'),
('VT000003', 'Chỉ may polyester 40/2 trắng', 'Chỉ may polyester 40/2 màu trắng', 'CUON', 'THREAD'),
('VT000004', 'Nút nhựa 4 lỗ 18L trắng', 'Nút nhựa 4 lỗ size 18L', 'PCS', 'ACCESSORY'),
('VT000005', 'Dây kéo nylon số 5 đen', 'Dây kéo nylon #5 màu đen', 'PCS', 'ACCESSORY'),
('VT000006', 'Thùng carton 5 lớp 60x40x40', 'Thùng carton đóng gói thành phẩm', 'PCS', 'PACKING'),
('VT000007', 'Túi PE 40x60 cm', 'Túi PE trong đóng gói sản phẩm', 'PCS', 'PACKING'),
('VT000008', 'Tem barcode 50x30 mm', 'Tem barcode decal nhiệt 50x30 mm', 'ROLL', 'PACKING'),
('VT000009', 'Dầu máy may công nghiệp', 'Dầu bôi trơn dùng cho máy may công nghiệp', 'L', 'MAINTENANCE'),
('VT000010', 'Kim máy may DBx1 số 11', 'Kim máy may công nghiệp DBx1 size 11', 'BOX', 'SPARE_PART'),
('VT000011', 'Găng tay bảo hộ phủ PU', 'Găng tay bảo hộ lao động phủ PU lòng bàn tay', 'PAIR', 'PPE'),
('VT000012', 'Băng keo OPP 48mm x 100y', 'Băng keo trong đóng thùng', 'ROLL', 'PACKING')
ON CONFLICT (material_code) DO UPDATE SET
    material_name = EXCLUDED.material_name,
    description = EXCLUDED.description,
    unit = EXCLUDED.unit,
    material_group = EXCLUDED.material_group;

INSERT INTO material_requests (
    request_no, requester_id, proposed_name, description, unit, material_group,
    status, masterdata_note, accounting_note, result_material_code, created_at, updated_at
)
SELECT * FROM (VALUES
('REQ-DEMO-0001',(SELECT id FROM users WHERE email='user@example.com'),'Vải thun cotton 2 chiều màu đen','Vải thun cotton 2 chiều, màu đen, khổ 1.8m, định lượng 180gsm','KG','FABRIC','PENDING_MASTERDATA',NULL,NULL,NULL,NOW()-INTERVAL '6 hours',NOW()-INTERVAL '6 hours'),
('REQ-DEMO-0002',(SELECT id FROM users WHERE email='user2@example.com'),'Khóa kéo YKK số 3 màu navy','Khóa kéo YKK #3 màu navy dùng cho áo khoác','PCS','ACCESSORY','PENDING_ACCOUNTING','Đã kiểm tra trùng mã, chưa có vật tư tương đương',NULL,NULL,NOW()-INTERVAL '1 day',NOW()-INTERVAL '3 hours'),
('REQ-DEMO-0003',(SELECT id FROM users WHERE email='user@example.com'),'Tem size dệt S-M-L-XL','Tem size dệt polyester bộ 4 size','PCS','LABEL','PENDING_CODE_ASSIGNMENT','Thông tin kỹ thuật phù hợp','Đã xác nhận nhóm tài khoản vật tư',NULL,NOW()-INTERVAL '2 days',NOW()-INTERVAL '4 hours'),
('REQ-DEMO-0004',(SELECT id FROM users WHERE email='user2@example.com'),'Túi zipper PE 30x40 cm','Túi zipper trong 30x40cm dùng đóng gói phụ kiện','PCS','PACKING','RETURNED_TO_REQUESTER','Cần bổ sung độ dày túi và quy cách đóng gói',NULL,NULL,NOW()-INTERVAL '3 days',NOW()-INTERVAL '1 hour'),
('REQ-DEMO-0005',(SELECT id FROM users WHERE email='user@example.com'),'Nhãn hướng dẫn giặt 4x8 cm','Nhãn satin in hướng dẫn giặt','PCS','LABEL','COMPLETED','Đã duyệt','Đã duyệt','VT000101',NOW()-INTERVAL '5 days',NOW()-INTERVAL '2 days')
) AS v(request_no, requester_id, proposed_name, description, unit, material_group, status, masterdata_note, accounting_note, result_material_code, created_at, updated_at)
WHERE NOT EXISTS (SELECT 1 FROM material_requests r WHERE r.request_no=v.request_no);

INSERT INTO request_history (request_id, actor_id, action, from_status, to_status, note, created_at)
SELECT r.id, u.id, 'CREATE_REQUEST', NULL, r.status,
       'Dữ liệu mẫu phục vụ kiểm thử Material Masterdata Portal', r.created_at
FROM material_requests r
JOIN users u ON u.email = CASE WHEN r.request_no IN ('REQ-DEMO-0002','REQ-DEMO-0004') THEN 'user2@example.com' ELSE 'user@example.com' END
WHERE r.request_no LIKE 'REQ-DEMO-%'
AND NOT EXISTS (SELECT 1 FROM request_history h WHERE h.request_id=r.id AND h.action='CREATE_REQUEST');

INSERT INTO request_history (request_id, actor_id, action, from_status, to_status, note, created_at)
SELECT r.id, u.id, 'RETURN', 'PENDING_MASTERDATA', 'RETURNED_TO_REQUESTER',
       'Cần bổ sung độ dày túi và quy cách đóng gói', NOW()-INTERVAL '1 hour'
FROM material_requests r
JOIN users u ON u.email='masterdata@example.com'
WHERE r.request_no='REQ-DEMO-0004'
AND NOT EXISTS (SELECT 1 FROM request_history h WHERE h.request_id=r.id AND h.action='RETURN');
