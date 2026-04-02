import requests
import re
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Craw dvid of Ministries and Agencies
def extract_all_dvids():
    agencies_slugs = [
        "bocongan", "bocongthuong", "bogiaoducdaotao", "bogiaothong", 
        "bokehoachvadautu", "bokhoahoccongnghe", "bolaodong", "bonongnghiep", 
        "bonoivu", "bongoaigiao", "boquocphong", "botaichinh", "botainguyen", 
        "botuphap", "bothongtin", "bovanhoathethao", "boxaydung", "boyte", 
        "nganhangnhanuoc", "thanhtrachinhphu", "uybandantoc", "vanphongchinhphu",
        "kiemtoannhanuoc", "toaannhandantoicao", "vienkiemsatnhandantoicao"
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    final_results = {}
    print(f"🚀 Bắt đầu quét dvid cho {len(agencies_slugs)} Bộ/Ngành...")

    for slug in agencies_slugs:
        url = f"https://vbpl.vn/{slug}/Pages/Home.aspx"
        try:
            print(f"🔎 Đang lấy dvid cho: {slug}...", end=" ", flush=True)
            response = requests.get(url, headers=headers, timeout=15)
            match = re.search(r'dvid=(\d+)', response.text)
            
            if match:
                dvid = match.group(1)
                final_results[slug] = {
                    "slug": slug,
                    "dvid": dvid,
                    "search_url": f"https://vbpl.vn/{slug}/Pages/vbpq-timkiem.aspx?dvid={dvid}"
                }
                print(f"✅ OK (dvid={dvid})")
            else:
                print("❌ Không thấy dvid")
            time.sleep(0.3) 

        except Exception as e:
            print(f"❌ Lỗi tại {slug}: {e}")

    return final_results

if __name__ == "__main__":
    results = extract_all_dvids()
    
    if results:
        save_path = os.getenv("JSON_SAVE_PATH")
        
        if not save_path:
            print("❌ LỖI: Chưa cấu hình JSON_SAVE_PATH trong file .env!")
        else:
            try:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=4)
                
                print(f"\n🏆 THÀNH CÔNG!")
                print(f"📂 File đã được lưu tại: {save_path}")
                print(f"📊 Tổng cộng: {len(results)} Bộ/Ngành đã được cấu hình.")
            except Exception as e:
                print(f"❌ Lỗi khi lưu file: {e}")