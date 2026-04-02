import os
import re
import time
import random
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException

# 1. TẢI CẤU HÌNH
load_dotenv()
MAX_PAGES = int(os.getenv("MAX_PAGES_PER_AGENCY", 100))
OUTPUT_DIR = os.getenv("ITEM_IDS_DIR", "/home/gnut_2004/Project/Rag/vietnam_law/data/raw/item_ids")

# DANH SÁCH CÁC BỘ CẦN QUÉT (Bạn có thể bỏ comment các bộ đã xong)
AGENCIES_DATA = {
    "bocongan": {"slug": "bocongan", "dvid": "316"},
    "bocongthuong": {"slug": "bocongthuong", "dvid": "218"},
    "bogiaoducdaotao": {"slug": "bogiaoducdaotao", "dvid": "317"},
    "bogiaothong": {"slug": "bogiaothong", "dvid": "315"},
    "bokehoachvadautu": {"slug": "bokehoachvadautu", "dvid": "312"},
    "bokhoahoccongnghe": {"slug": "bokhoahoccongnghe", "dvid": "213"},
    "bolaodong": {"slug": "bolaodong", "dvid": "318"},
    "bonongnghiep": {"slug": "bonongnghiep", "dvid": "319"},
    "bonoivu": {"slug": "bonoivu", "dvid": "320"},
    "bongoaigiao": {"slug": "bongoaigiao", "dvid": "211"},
    "boquocphong": {"slug": "boquocphong", "dvid": "314"},
    "botaichinh": {"slug": "botaichinh", "dvid": "281"},
    "botainguyen": {"slug": "botainguyen", "dvid": "321"},
    "botuphap": {"slug": "botuphap", "dvid": "41"},
    "bothongtin": {"slug": "bothongtin", "dvid": "322"},
    "bovanhoathethao": {"slug": "bovanhoathethao", "dvid": "323"},
    "boxaydung": {"slug": "boxaydung", "dvid": "324"},
    "boyte": {"slug": "boyte", "dvid": "325"},
    "nganhangnhanuoc": {"slug": "nganhangnhanuoc", "dvid": "326"},
    "thanhtrachinhphu": {"slug": "thanhtrachinhphu", "dvid": "327"},
    "uybandantoc": {"slug": "uybandantoc", "dvid": "328"},
    "vanphongchinhphu": {"slug": "vanphongchinhphu", "dvid": "329"},
    "kiemtoannhanuoc": {"slug": "kiemtoannhanuoc", "dvid": "330"},
    "toaannhandantoicao": {"slug": "toaannhandantoicao", "dvid": "331"},
    "vienkiemsatnhandantoicao": {"slug": "vienkiemsatnhandantoicao", "dvid": "332"}
}

def init_driver():
    """Khởi tạo Chrome với cấu hình tránh bị treo"""
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(90) # Tránh đợi vô hạn khi mạng lag
    return driver

def save_ids_realtime(slug, ids_set):
    """Ghi ID xuống file ngay lập tức"""
    file_path = os.path.join(OUTPUT_DIR, f"{slug}.txt")
    with open(file_path, 'w', encoding='utf-8') as f:
        for item_id in sorted(ids_set, key=int, reverse=True):
            f.write(f"{item_id}\n")

def crawl_agency_selenium(driver, slug, dvid):
    found_ids = set()
    url = f"https://vbpl.vn/{slug}/Pages/vbpq-timkiem.aspx?dvid={dvid}"
    print(f"\n🚀 Đang xử lý: {slug.upper()}")
    
    driver.get(url)
    wait = WebDriverWait(driver, 30)

    try:
        # --- BƯỚC 1: ÉP CHỌN "TẤT CẢ" VÀ TÌM KIẾM ---
        print("   ⚙️ Đang gỡ bỏ bộ lọc mặc định (Ép chọn 'Tất cả')...")
        script_force_all = """
            var selects = document.querySelectorAll('select');
            selects.forEach(s => {
                if(s.id.includes('loaiVb') || s.id.includes('tinhtrang')) {
                    s.selectedIndex = 0; 
                }
            });
            // Gọi lệnh PostBack chính chủ của ASP.NET để tìm kiếm
            var btn = document.querySelector('input[id*="btnTimKiem"]');
            if(btn) { __doPostBack(btn.name, ''); }
            else { document.forms[0].submit(); }
        """
        driver.execute_script(script_force_all)
        time.sleep(7) # Đợi server xử lý kho dữ liệu lớn

        # --- BƯỚC 2: CÀO VÀ NEXT TRANG ---
        for page in range(1, MAX_PAGES + 1):
            try:
                # Đợi văn bản xuất hiện
                wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'ItemID=')]")))
            except:
                print(f"      📄 Trang {page}: Không thấy dữ liệu (Hết kho).")
                break

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            links = soup.find_all('a', href=re.compile(r'ItemID=\d+'))
            page_ids = {re.search(r'ItemID=(\d+)', l.get('href')).group(1) for l in links}

            if not page_ids: break
            
            # Check lặp trang (Phòng khi click Next không ăn)
            if page > 1 and page_ids.issubset(found_ids):
                print(f"      🛑 Cảnh báo lặp Trang 1. Server không chuyển trang.")
                break

            found_ids.update(page_ids)
            save_ids_realtime(slug, found_ids)
            print(f"      📄 Trang {page}: +{len(page_ids)} ID (Tổng: {len(found_ids)})")

            if page >= MAX_PAGES: break

            # --- BƯỚC 3: CLICK NEXT LÌ LỢM ---
            next_page = page + 1
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            success_next = False
            # Các kiểu XPath cho nút phân trang của VBPL
            pager_xpaths = [
                f"//div[contains(@id, 'Pager')]//a[text()='{next_page}']",
                f"//a[contains(@href, 'Pager') and text()='{next_page}']",
                f"//a[text()='{next_page}']"
            ]
            
            for xpath in pager_xpaths:
                try:
                    btn_next = driver.find_element(By.XPATH, xpath)
                    driver.execute_script("arguments[0].click();", btn_next)
                    success_next = True
                    break
                except: continue
                
            if not success_next:
                print(f"      🛑 Không thấy nút trang {next_page}. Hết dữ liệu thực tế.")
                break
                
            time.sleep(random.uniform(5, 8)) # Nghỉ để tránh bị Ban IP
                
    except Exception as e:
        print(f"      ❌ Lỗi: {str(e)[:100]}")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for slug, data in AGENCIES_DATA.items():
        driver = None
        try:
            driver = init_driver()
            crawl_agency_selenium(driver, slug, data['dvid'])
            print(f"   ✅ Hoàn thành Bộ: {slug.upper()}")
        except (TimeoutException, WebDriverException):
            print(f"   ⚠️ Driver bị treo tại Bộ {slug}. Đang khởi động lại...")
        except Exception as e:
            print(f"   ❌ Lỗi nặng: {e}")
        finally:
            if driver:
                try: driver.quit()
                except: pass
            time.sleep(10) # Nghỉ giữa các Bộ

    print("\n🏁 TẤT CẢ QUÁ TRÌNH CÀO ID ĐÃ KẾT THÚC!")

if __name__ == "__main__":
    main()