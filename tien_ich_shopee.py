"""
Tên file: shopee_api.py
Chức năng: Module xử lý toàn bộ logic liên quan đến Shopee Open API v2 cho Affiliate Tool.
"""

import time
import hmac
import hashlib
import requests
import re
import logging

# Cấu hình logging để theo dõi luồng chạy trong terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class ShopeeAffiliateManager:
    """
    Class quản lý các tương tác với Shopee Open API v2 dành cho Affiliate.
    """

    def __init__(self, partner_id, partner_key, app_id=None):
        """
        Hàm khởi tạo.
        
        Tham số:
        - partner_id (int/str): ID đối tác do Shopee cấp.
        - partner_key (str): Khóa bí mật (Secret Key) do Shopee cấp để tạo chữ ký.
        - app_id (int/str, optional): App ID, nếu không truyền sẽ dùng mặc định là partner_id.
        """
        self.partner_id = str(partner_id)
        self.partner_key = partner_key.encode('utf-8')
        self.app_id = str(app_id) if app_id else self.partner_id
        # Host chuẩn của Shopee Open API v2
        self.host = "https://partner.shopeemobile.com"
        logging.info("Khởi tạo ShopeeAffiliateManager thành công.")

    def _generate_signature(self, path):
        """
        Tạo chữ ký (signature) cho Request dựa trên chuẩn Shopee Open API v2.
        
        Tham số:
        - path (str): Đường dẫn API (vd: '/api/v2/affiliate/generate_short_link').
        
        Output:
        - tuple: (signature, timestamp)
        """
        timestamp = int(time.time())
        # Công thức: partner_id + path + timestamp
        base_string = f"{self.partner_id}{path}{timestamp}".encode('utf-8')
        
        # Băm bằng thuật toán HMAC-SHA256 với secret là partner_key
        sign = hmac.new(self.partner_key, base_string, hashlib.sha256).hexdigest()
        
        logging.debug(f"Đã tạo signature cho path {path}. Timestamp: {timestamp}")
        return sign, timestamp

    def _call_api(self, path, payload):
        """
        Hàm private hỗ trợ gọi API với cấu hình Headers và Query params chuẩn v2.
        """
        sign, timestamp = self._generate_signature(path)
        
        # Shopee v2 yêu cầu auth params nằm trên URL query string
        url = f"{self.host}{path}?partner_id={self.partner_id}&timestamp={timestamp}&sign={sign}"
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            logging.info(f"Đang gửi request tới API: {path}")
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()  # Bắt lỗi HTTP (4xx, 5xx)
            return response.json()
        except requests.exceptions.Timeout:
            error_msg = f"Lỗi: Request tới {path} bị quá thời gian (Timeout)."
            logging.error(error_msg)
            return {"error": error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"Lỗi mạng hoặc lỗi API khi gọi {path}: {str(e)}"
            logging.error(error_msg)
            return {"error": error_msg}

    def get_custom_link(self, original_url):
        """
        Tạo link rút gọn (Short Link) Affiliate từ link sản phẩm gốc.
        
        Tham số:
        - original_url (str): Link sản phẩm Shopee gốc.
        
        Output:
        - dict: Kết quả trả về từ API chứa short_link hoặc thông báo lỗi.
        """
        path = "/api/v2/affiliate/generate_short_link"
        payload = {
            "originUrl": original_url
        }
        
        logging.info(f"Yêu cầu tạo link Affiliate cho: {original_url}")
        return self._call_api(path, payload)

    def get_item_vouchers(self, item_id, shop_id):
        """
        Lấy danh sách Voucher hoặc thông tin khuyến mãi của sản phẩm.
        
        Tham số:
        - item_id (str/int): ID của sản phẩm.
        - shop_id (str/int): ID của Shop.
        
        Output:
        - dict: Dữ liệu JSON chứa thông tin vouchers/khuyến mãi hoặc thông báo lỗi.
        """
        # Lưu ý: Endpoint này mang tính minh họa dựa trên cấu trúc v2. 
        # Cần thay đổi path thực tế tuỳ thuộc vào việc App được cấp quyền gọi API khuyến mãi nào.
        path = "/api/v2/affiliate/product/get_product_detail" 
        
        payload = {
            "item_id": int(item_id),
            "shop_id": int(shop_id)
        }
        
        logging.info(f"Đang lấy thông tin Voucher cho Item ID: {item_id}, Shop ID: {shop_id}")
        return self._call_api(path, payload)

    def parse_url(self, url):
        """
        Parser thông minh: Trích xuất item_id và shop_id từ nhiều định dạng link Shopee.
        Hỗ trợ link PC, link Mobile, và tự động phân giải (unshorten) link marketing rút gọn.
        
        Tham số:
        - url (str): Link Shopee đầu vào.
        
        Output:
        - dict: Gồm {"shop_id": "...", "item_id": "..."} hoặc None/lỗi.
        """
        logging.info(f"Đang parse URL: {url}")
        
        try:
            # Xử lý nếu là link rút gọn (shp.ee, s.shopee.vn). Cần phân giải ra link gốc trước.
            if "shp.ee" in url or "s.shopee.vn" in url:
                logging.info("Phát hiện link rút gọn, đang tiến hành phân giải (resolve)...")
                res = requests.get(url, allow_redirects=True, timeout=10)
                url = res.url
                logging.info(f"Link sau khi phân giải: {url}")

            # Pattern 1: Link PC chuẩn (VD: shopee.vn/Ten-San-Pham-i.12345.67890)
            pattern_pc = r"-i\.(\d+)\.(\d+)"
            # Pattern 2: Link Mobile/App (VD: shopee.vn/product/12345/67890)
            pattern_mobile = r"/product/(\d+)/(\d+)"
            
            # Ưu tiên kiểm tra định dạng PC
            match_pc = re.search(pattern_pc, url)
            if match_pc:
                shop_id, item_id = match_pc.groups()
                logging.info(f"Bóc tách thành công (PC format) -> Shop ID: {shop_id}, Item ID: {item_id}")
                return {"shop_id": shop_id, "item_id": item_id}
            
            # Tiếp tục kiểm tra định dạng Mobile
            match_mobile = re.search(pattern_mobile, url)
            if match_mobile:
                shop_id, item_id = match_mobile.groups()
                logging.info(f"Bóc tách thành công (Mobile format) -> Shop ID: {shop_id}, Item ID: {item_id}")
                return {"shop_id": shop_id, "item_id": item_id}

            logging.warning("Không tìm thấy shop_id và item_id trong URL được cung cấp.")
            return None

        except requests.exceptions.RequestException as e:
            error_msg = f"Lỗi mạng khi cố gắng phân giải link rút gọn: {str(e)}"
            logging.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Lỗi không xác định khi parse URL: {str(e)}"
            logging.error(error_msg)
            return {"error": error_msg}