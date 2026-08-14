CREATE TABLE IF NOT EXISTS categories (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS brands (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

ALTER TABLE materials ADD COLUMN IF NOT EXISTS category_id BIGINT REFERENCES categories(id);
ALTER TABLE materials ADD COLUMN IF NOT EXISTS brand_id BIGINT REFERENCES brands(id);
ALTER TABLE material_requests ADD COLUMN IF NOT EXISTS category_id BIGINT REFERENCES categories(id);
ALTER TABLE material_requests ADD COLUMN IF NOT EXISTS brand_id BIGINT REFERENCES brands(id);
CREATE INDEX IF NOT EXISTS idx_materials_category_id ON materials(category_id);
CREATE INDEX IF NOT EXISTS idx_materials_brand_id ON materials(brand_id);

INSERT INTO categories(code,name) VALUES
('LAPTOP','Laptop'),('DESKTOP','Máy tính bàn'),('PRINTER','Máy in'),('MOBILE','Thiết bị di động'),
('MOUSE','Chuột máy tính'),('KEYBOARD','Bàn phím'),('MONITOR','Màn hình'),('STORAGE','Đĩa cứng & thiết bị lưu trữ'),
('SWITCH','Thiết bị chuyển mạch'),('WIFI','Thiết bị Wifi'),('SERVER','Máy chủ'),('UPS','UPS & thiết bị nguồn'),
('CCTV','Camera & giám sát'),('BARCODE','Máy quét mã vạch'),('LABEL_PRINTER','Máy in tem nhãn'),
('IT_EQUIPMENT','Thiết bị CNTT khác'),('SEWING_MACHINE','Máy may công nghiệp'),('CUTTING_MACHINE','Máy cắt'),
('SPREADING_MACHINE','Máy trải vải'),('EMBROIDERY_MACHINE','Máy thêu'),('FABRIC_PRINTER','Máy in vải'),
('PRESSING_MACHINE','Máy ép & máy ủi'),('NEEDLE_DETECTOR','Máy dò kim'),('QC_EQUIPMENT','Thiết bị kiểm tra chất lượng'),
('GARMENT_AUXILIARY','Thiết bị phụ trợ ngành may'),('MACHINE_SPARE_PART','Phụ tùng máy'),('ELECTRICAL','Thiết bị điện'),
('MECHANICAL','Thiết bị cơ khí'),('PNEUMATIC','Thiết bị khí nén'),('SAFETY','Thiết bị an toàn & PCCC'),
('OFFICE_EQUIPMENT','Thiết bị văn phòng')
ON CONFLICT(code) DO UPDATE SET name=EXCLUDED.name,is_active=TRUE;

INSERT INTO brands(code,name) VALUES
('MULTI','Đa nhãn hiệu'),('NO_BRAND','Không nhãn hiệu'),('JACK','Jack'),('UGREEN','UGreen'),
('DELL','Dell'),('HP','HP'),('LENOVO','Lenovo'),('ASUS','Asus'),('ACER','Acer'),('APPLE','Apple'),
('SAMSUNG','Samsung'),('LOGITECH','Logitech'),('MICROSOFT','Microsoft'),('KINGSTON','Kingston'),
('SEAGATE','Seagate'),('WESTERN_DIGITAL','Western Digital'),('CISCO','Cisco'),('ARUBA','Aruba'),('TP_LINK','TP-Link'),
('MIKROTIK','MikroTik'),('UBIQUITI','Ubiquiti'),('FORTINET','Fortinet'),('APC','APC'),('HIKVISION','Hikvision'),
('DAHUA','Dahua'),('ZEBRA','Zebra'),('HONEYWELL','Honeywell'),('BROTHER','Brother'),('CANON','Canon'),
('EPSON','Epson'),('RICOH','Ricoh'),('JUKI','Juki'),('PEGASUS','Pegasus'),('KANSAI','Kansai Special'),
('SIRUBA','Siruba'),('YAMATO','Yamato'),('HASHIMA','Hashima'),('EASTMAN','Eastman'),('GERBER','Gerber'),
('LECTRA','Lectra'),('MORGAN','Morgan Tecnica'),('TAJIMA','Tajima'),('BARUDAN','Barudan'),('ZOJE','Zoje'),
('TYPICAL','Typical'),('JACK_SEWING','Jack Sewing')
ON CONFLICT(code) DO UPDATE SET name=EXCLUDED.name,is_active=TRUE;
