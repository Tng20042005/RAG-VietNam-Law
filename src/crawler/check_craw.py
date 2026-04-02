import os
from dotenv import load_dotenv

load_dotenv()

ID_SOURCE_DIR = os.getenv("ITEM_IDS_DIR")
CONTENTS_DIR = os.getenv("CONTENTS_OUTPUT_DIR")

def check_progress():
    print(f"{'Bộ / Ngành':<30} | {'Số ID':<10} | {'Đã cào':<10} | {'Tiến độ':<10} | {'Thiếu'}")
    print("-" * 80)

    total_ids = 0
    total_contents = 0

    # Lấy danh sách các file ID
    id_files = sorted([f for f in os.listdir(ID_SOURCE_DIR) if f.endswith('.txt')])

    for id_file in id_files:
        agency_name = os.path.splitext(id_file)[0]
        id_file_path = os.path.join(ID_SOURCE_DIR, id_file)
        
        # 1. Đếm số ID mục tiêu
        with open(id_file_path, 'r', encoding='utf-8') as f:
            ids = [line.strip() for line in f if line.strip()]
            num_ids = len(ids)
        
        # 2. Đếm số file nội dung thực tế
        agency_content_path = os.path.join(CONTENTS_DIR, agency_name)
        num_contents = 0
        if os.path.exists(agency_content_path):
            num_contents = len([f for f in os.listdir(agency_content_path) if f.endswith('.txt')])
        
        # 3. Tính toán
        missing = num_ids - num_contents
        progress = (num_contents / num_ids * 100) if num_ids > 0 else 0
        
        total_ids += num_ids
        total_contents += num_contents

        # In kết quả từng dòng
        color = "\033[92m" if missing == 0 else "\033[93m" if progress > 50 else "\033[91m"
        reset = "\033[0m"
        print(f"{agency_name:<30} | {num_ids:<10} | {num_contents:<10} | {color}{progress:>6.1f}%{reset}  | {missing}")

    print("-" * 80)
    total_progress = (total_contents / total_ids * 100) if total_ids > 0 else 0
    print(f"{'TỔNG CỘNG':<30} | {total_ids:<10} | {total_contents:<10} | {total_progress:>6.1f}%  | {total_ids - total_contents}")

if __name__ == "__main__":
    if not ID_SOURCE_DIR or not CONTENTS_DIR:
        print("❌ Lỗi: Kiểm tra lại đường dẫn trong file .env!")
    else:
        check_progress()