import requests
from bs4 import BeautifulSoup
import os
import time
from dotenv import load_dotenv
import re
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

ID_SOURCE_DIR = os.getenv("ITEM_IDS_DIR")
BASE_OUTPUT_DIR = os.getenv("CONTENTS_OUTPUT_DIR")

def crawl_vbpl_content(item_id, agency_name, agency_folder):
    file_path = os.path.join(agency_folder, f"{item_id}.txt")
    if os.path.exists(file_path):
        return True, "SKIPPED (Đã có file)"
    
    url = f"https://vbpl.vn/{agency_name}/Pages/vbpq-toanvan.aspx?ItemID={item_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 404:
            url = f"https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID={item_id}"
            response = requests.get(url, headers=headers, timeout=30)
            
        response.raise_for_status()
        response.encoding = 'utf-8' # Ép kiểu utf-8 để tránh lỗi font tiếng Việt
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- 1. LẤY TIÊU ĐỀ ---
        title_tag = soup.find('div', class_='title') or soup.find('p', class_='title')
        title = title_tag.get_text(strip=True) if title_tag else f"Văn bản ID {item_id}"
        
        # --- 2. LẤY METADATA (HIỆU LỰC & NGÀY) ---
        status = "N/A"
        effective_date = "N/A"
        
        # Thẻ đỏ: Trạng thái
        status_tag = soup.find('li', class_='red')
        if status_tag:
            status = status_tag.get_text(strip=True).replace("Hiệu lực:", "").strip()
        
        # Thẻ xanh: Ngày có hiệu lực
        date_tag = soup.find('li', class_='green')
        if date_tag:
            effective_date = date_tag.get_text(strip=True).replace("Ngày có hiệu lực:", "").strip()

        # --- 3. LẤY NGÀY SOẠN THẢO/KÝ (TỪ THẺ <i> HOẶC TIÊU ĐỀ) ---
        signed_date = "N/A"
        date_pattern = r'[Nn]gày\s+(\d+)\s+tháng\s+(\d+)\s+năm\s+(\d{4})'
        
        # Quét qua các thẻ <i> để tìm dòng "Hà Nội, ngày... tháng... năm..."
        all_italics = soup.find_all('i')
        for italic in all_italics:
            italic_text = italic.get_text(strip=True)
            match = re.search(date_pattern, italic_text)
            if match:
                day, month, year = match.groups()
                signed_date = f"{day.zfill(2)}/{month.zfill(2)}/{year}"
                break

        # --- 4. TÍNH NĂM LỌC (FILTER_YEAR) ---
        filter_year = 0
        # Ưu tiên lấy năm từ ngày hiệu lực, nếu không có thì lấy từ ngày ký
        check_date = effective_date if effective_date != "N/A" else signed_date
        year_match = re.search(r'\d{4}', check_date)
        if year_match:
            filter_year = year_match.group()

        # --- 5. LẤY NỘI DUNG TOÀN VĂN ---
        content_tag = (
            soup.find('div', {'id': 'divNoiDung'}) or 
            soup.find('div', class_='toanvancontent') or 
            soup.find('div', class_='fulltext')
        )

        if content_tag:
            # Xóa các phần rác/thẻ metadata hiển thị lặp lại trong nội dung để text sạch
            for trash in content_tag.find_all('div', class_='vbInfo'):
                trash.decompose()

            text_content = content_tag.get_text(separator='\n', strip=True)
            
            # --- 6. GHI FILE VỚI CẤU TRÚC ĐẦY ĐỦ ---
            final_data = f"SOURCE_URL: {url}\n"
            final_data += f"TITLE: {title}\n"
            final_data += f"ITEM_ID: {item_id}\n"
            final_data += f"STATUS: {status}\n"
            final_data += f"EFFECTIVE_DATE: {effective_date}\n"
            final_data += f"SIGNED_DATE: {signed_date}\n"  # Field mới
            final_data += f"FILTER_YEAR: {filter_year}\n" # Field mới dùng để RAG lọc theo năm
            final_data += "="*50 + "\n\n"
            final_data += text_content
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(final_data)
            return True, f"DOWNLOADED (Status: {status}, Year: {filter_year})"
        else:
            return False, "EMPTY (Không tìm thấy nội dung toàn văn)"
            
    except Exception as e:
        return False, f"ERROR: {str(e)}"

# Giữ nguyên hàm main() như cũ của bạn...
def main():
    if not os.path.exists(ID_SOURCE_DIR):
        print(f"❌ Lỗi: Thư mục nguồn {ID_SOURCE_DIR} không tồn tại!")
        return

    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
    
    id_files = [f for f in os.listdir(ID_SOURCE_DIR) if f.endswith('.txt')]
    
    print(f"🚀 Bắt đầu cào nội dung cho {len(id_files)} Bộ/Ngành...")

    for id_file in id_files:
        agency_name = os.path.splitext(id_file)[0]
        agency_folder = os.path.join(BASE_OUTPUT_DIR, agency_name)
        os.makedirs(agency_folder, exist_ok=True)
        
        id_file_path = os.path.join(ID_SOURCE_DIR, id_file)
        with open(id_file_path, 'r', encoding='utf-8') as f:
            ids = [line.strip() for line in f if line.strip()]
        
        print(f"\n📂 Thư mục: {agency_name.upper()} ({len(ids)} ID)")

        for index, item_id in enumerate(ids, 1):
            print(f"  [{index}/{len(ids)}] ID {item_id}:", end=" ", flush=True)
            
            success, msg = crawl_vbpl_content(item_id, agency_name, agency_folder)
            
            if success:
                print(f"✅ {msg}")
            else:
                print(f"❌ {msg}")
            
            # Nghỉ một chút để tránh bị server chặn (Rate limit)
            if "DOWNLOADED" in msg:
                time.sleep(1.2) 

    print("\n🏁 TẤT CẢ ĐÃ HOÀN TẤT!")

if __name__ == "__main__":
    main()