import os
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# Nạp class ShopeeAffiliateManager từ module bạn đã viết
from tien_ich_shopee import ShopeeAffiliateManager

# Bước 1: Nạp các biến môi trường từ file .env
load_dotenv()

# Lấy các mã bí mật từ hệ thống môi trường
PARTNER_ID = os.getenv("PARTNER_ID")
PARTNER_KEY = os.getenv("PARTNER_KEY")

# Kiểm tra xem file .env đã được cấu hình đúng chưa để tránh lỗi ứng dụng
if not PARTNER_ID or not PARTNER_KEY:
    raise ValueError("Lỗi: Thiếu PARTNER_ID hoặc PARTNER_KEY trong file .env")

# Bước 2: Khởi tạo ứng dụng Flask
app = Flask(__name__)

# Bước 3: Khởi tạo công cụ quản lý Shopee Affiliate
shopee_manager = ShopeeAffiliateManager(partner_id=PARTNER_ID, partner_key=PARTNER_KEY)


# Bước 4: Viết hàm điều hướng cho trang chủ
@app.route('/')
def trang_chu():
    """
    Hàm xử lý khi người dùng truy cập vào trang chủ.
    Sẽ render và trả về giao diện HTML từ thư mục templates.
    """
    # Giao diện được lưu trong thư mục templates/giao_dien.html
    return render_template('giao_dien.html')


# Bước 5: Viết hàm API xử lý dữ liệu và chuyển đổi link
@app.route('/api/chuyen-doi', methods=['POST'])
def xu_ly_link():
    """
    Hàm API nhận đường dẫn Shopee từ giao diện, bóc tách ID, 
    chuyển đổi link Affiliate và lấy thông tin mã giảm giá.
    """
    try:
        # Nhận dữ liệu JSON từ request của trình duyệt
        du_lieu_nhan = request.get_json()
        
        # Kiểm tra xem có gửi link lên không
        if not du_lieu_nhan or 'url' not in du_lieu_nhan:
            return jsonify({
                "thanh_cong": False,
                "thong_bao_loi": "Vui lòng cung cấp đường dẫn (URL) sản phẩm Shopee."
            }), 400
            
        duong_dan_goc = du_lieu_nhan['url']

        # 1. Gọi hàm parser thông minh để tách item_id và shop_id
        thong_tin_id = shopee_manager.parse_url(duong_dan_goc)

        # Xử lý lỗi nếu link không hợp lệ hoặc không bóc tách được
        if not thong_tin_id or 'error' in thong_tin_id:
            loi_chi_tiet = thong_tin_id.get('error') if thong_tin_id else "Không thể trích xuất ID sản phẩm từ link cung cấp. Vui lòng kiểm tra lại link."
            return jsonify({
                "thanh_cong": False,
                "thong_bao_loi": loi_chi_tiet
            }), 400

        item_id = thong_tin_id['item_id']
        shop_id = thong_tin_id['shop_id']

        # 2. Gọi API tạo link Affiliate rút gọn
        du_lieu_link = shopee_manager.get_custom_link(duong_dan_goc)
        
        # Nếu gọi API tạo link bị lỗi
        if 'error' in du_lieu_link:
            return jsonify({
                "thanh_cong": False,
                "thong_bao_loi": f"Lỗi tạo link Affiliate: {du_lieu_link['error']}"
            }), 500

        # 3. Gọi API lấy thông tin mã giảm giá / voucher của sản phẩm
        du_lieu_voucher = shopee_manager.get_item_vouchers(item_id, shop_id)

        # 4. Tổng hợp kết quả và trả về cho giao diện web
        ket_qua_tong_hop = {
            "thanh_cong": True,
            "thong_tin_id": {
                "item_id": item_id,
                "shop_id": shop_id
            },
            "ket_qua_link_affiliate": du_lieu_link,
            "ket_qua_voucher": du_lieu_voucher
        }
        
        return jsonify(ket_qua_tong_hop), 200

    except Exception as e:
        # Bắt các lỗi không xác định trong quá trình xử lý server
        return jsonify({
            "thanh_cong": False,
            "thong_bao_loi": f"Đã xảy ra lỗi trên hệ thống: {str(e)}"
        }), 500


# Bước 6: Lệnh chạy server Flask
if __name__ == '__main__':
    # Chạy server ở chế độ debug để dễ dàng theo dõi lỗi trong terminal
    app.run(debug=True, host='0.0.0.0', port=5000)