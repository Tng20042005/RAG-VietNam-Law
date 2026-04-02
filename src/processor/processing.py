
# import re
# import os
# import sys
# import json
# import html
# from dotenv import load_dotenv

# CONTENTS_OUTPUT_DIR = os.getenv("CONTENTS_OUTPUT_DIR")
# JSON_CHUNKS_DIR = os.getenv("JSON_CHUNKS_DIR")

# if sys.stdout.encoding != 'utf-8':
#     sys.stdout.reconfigure(encoding='utf-8')

# # Process Struct of Content
# def legal_pro_rag_splitter_v15(full_content):
#     """
#     Giữ nguyên logic tách Điều/Điều thứ/Điều số và Parent-Child Anchor của bản v15.
#     """
#     full_content = html.unescape(full_content)
#     parts = full_content.split("-" * 50)
#     header_raw = parts[0] if len(parts) >= 2 else ""
#     raw_body = parts[1] if len(parts) >= 2 else full_content

#     title_match = re.search(r"TITLE: (.*)", header_raw)
#     id_match = re.search(r"ITEM_ID: (.*)", header_raw)
#     url_match = re.search(r"SOURCE_URL: (.*)", header_raw)

#     metadata = {
#         "title": title_match.group(1).strip() if title_match else "N/A",
#         "id": id_match.group(1).strip() if id_match else "N/A",
#         "url": url_match.group(1).strip() if url_match else "N/A"
#     }
    
#     source_label = (
#         f"--- 📚 NGUỒN DỮ LIỆU LUẬT VIỆT NAM ---\n"
#         f"📄 TIÊU ĐỀ: {metadata['title']}\n"
#         f"🆔 ĐỊNH DANH (ID): {metadata['id']}\n"
#         f"🔗 SOURCE_URL: {metadata['url']}\n"
#         f"--------------------------------------\n"
#     )

#     body = re.sub(r'(Điều(?:\s+thứ|\s+số)?|Chương)[\s\n]+([IVXLCDM\d]+\.?)', r'\1 \2', raw_body, flags=re.IGNORECASE)
#     body = re.sub(r'[ \t]+', ' ', body)

#     chapter_blocks = re.split(r'\n(?=Chương\s+[IVXLCDM\d]+)', body, flags=re.IGNORECASE)
#     final_chunks = []
#     current_chapter = "PHẦN MỞ ĐẦU / CĂN CỨ"

#     for chapter_block in chapter_blocks:
#         chapter_block = chapter_block.strip()
#         if not chapter_block: continue

#         chapter_match = re.match(r'^(Chương\s+[IVXLCDM\d]+.*?)\n', chapter_block, flags=re.IGNORECASE)
#         if chapter_match:
#             current_chapter = chapter_match.group(1).strip().upper()

#         temp_splits = re.split(r'\n(?=Điều(?:\s+thứ|\s+số)?\s+\d+)', chapter_block, flags=re.IGNORECASE)
        
#         combined_articles = []
#         for split in temp_splits:
#             if not combined_articles:
#                 combined_articles.append(split)
#             else:
#                 last_line = combined_articles[-1].strip().split('\n')[-1]
#                 if re.search(r'\d+\.\s*$', last_line):
#                     combined_articles[-1] = combined_articles[-1] + "\n" + split
#                 else:
#                     combined_articles.append(split)

#         for art_block in combined_articles:
#             art_block = art_block.strip()
#             if not art_block: continue

#             if not re.match(r'^Điều(?:\s+thứ|\s+số)?', art_block, flags=re.IGNORECASE):
#                 final_chunks.append({
#                     "location": current_chapter,
#                     "content": f"{source_label}📍 VỊ TRÍ: {current_chapter}\n{art_block}",
#                     "metadata": metadata
#                 })
#                 continue

#             point_pattern = re.compile(r'\n\s*(\d+)\.(?:\s|\n|$)')
#             matches = list(point_pattern.finditer(art_block))
            
#             valid_split_indices = []
#             for m in matches:
#                 start_idx = m.start()
#                 following_text = art_block[start_idx:start_idx+150].lower()
#                 prefix = art_block[:start_idx]
#                 quote_count = prefix.count('"') + prefix.count('“') + prefix.count('”')
                
#                 if quote_count % 2 == 0:
#                     amending_keywords = r'(điều(?:\s+thứ|\s+số)?|khoản|điểm|chương|mục)\s+\d+|sửa đổi|bổ sung'
#                     if re.search(amending_keywords, following_text):
#                         valid_split_indices.append(start_idx)

#             if valid_split_indices:
#                 first_split = valid_split_indices[0]
#                 parent_anchor = art_block[:first_split].strip()
                
#                 for i in range(len(valid_split_indices)):
#                     start = valid_split_indices[i]
#                     end = valid_split_indices[i+1] if i+1 < len(valid_split_indices) else len(art_block)
#                     point_content = art_block[start:end].strip()
                    
#                     final_chunks.append({
#                         "location": current_chapter,
#                         "anchor": parent_anchor,
#                         "content": f"{source_label}📍 VỊ TRÍ: {current_chapter}\n👉 ⚖️ CĂN CỨ GỐC: {parent_anchor}\n\n📝 NỘI DUNG CHI TIẾT:\n{point_content}",
#                         "metadata": metadata
#                     })
#             else:
#                 final_chunks.append({
#                     "location": current_chapter,
#                     "content": f"{source_label}📍 VỊ TRÍ: {current_chapter}\n{art_block}",
#                     "metadata": metadata
#                 })

#     return final_chunks

# # Process all files
# def process_all_files():
#     print(f"🚀 Bắt đầu xử lý hàng loạt từ: {CONTENTS_OUTPUT_DIR_DIR}")
    
#     for root, dirs, files in os.walk(CONTENTS_OUTPUT_DIR_DIR):
#         for file in files:
#             if file.endswith(".txt"):
#                 input_file_path = os.path.join(root, file)
                
#                 relative_path = os.path.relpath(root, CONTENTS_OUTPUT_DIR_DIR)
#                 target_output_dir = os.path.join(OUTPUT_DIR, relative_path)
#                 os.makedirs(target_output_dir, exist_ok=True)
                
#                 output_file_name = file.replace(".txt", ".json")
#                 output_file_path = os.path.join(target_output_dir, output_file_name)
                
#                 print(f"📄 Đang xử lý: {relative_path}/{file} -> {output_file_name}")
                
#                 try:
#                     with open(input_file_path, 'r', encoding='utf-8') as f:
#                         data = f.read()
                    
#                     chunks = legal_pro_rag_splitter_v15(data)
                    
#                     output_data = {
#                         "filename": file,
#                         "total_chunks": len(chunks),
#                         "chunks": chunks
#                     }
                    
#                     with open(output_file_path, 'w', encoding='utf-8') as f:
#                         json.dump(output_data, f, ensure_ascii=False, indent=4)
                        
#                 except Exception as e:
#                     print(f"❌ Lỗi tại file {file}: {e}")

#     print(f"\n✅ HOÀN TẤT! Tất cả file JSON đã được lưu tại: {OUTPUT_DIR}")

# if __name__ == "__main__":
#     process_all_files()
import re
import os
import sys
import json
import html
from dotenv import load_dotenv

# LOAD CONFIG
load_dotenv()
# Fix lại tên biến cho đồng bộ với file .env của bạn
CONTENTS_OUTPUT_DIR = os.getenv("CONTENTS_OUTPUT_DIR", "/home/gnut_2004/Project/Rag/vietnam_law/data/raw/contents")
JSON_CHUNKS_DIR = os.getenv("JSON_CHUNKS_DIR", "/home/gnut_2004/Project/Rag/vietnam_law/data/processed/json_chunks")

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def legal_pro_rag_splitter_v16(full_content):
    """
    Bản v16: Hỗ trợ tách Metadata mới (Status, Date, Year) để phục vụ Filtering trong Vector DB.
    """
    full_content = html.unescape(full_content)
    parts = full_content.split("=" * 50)
    header_raw = parts[0] if len(parts) >= 2 else ""
    raw_body = parts[1] if len(parts) >= 2 else full_content

    # --- BÓC TÁCH METADATA NÂNG CAO ---
    def extract_meta(pattern, text, default="N/A"):
        match = re.search(pattern, text)
        return match.group(1).strip() if match else default

    title = extract_meta(r"TITLE: (.*)", header_raw)
    item_id = extract_meta(r"ITEM_ID: (.*)", header_raw)
    url = extract_meta(r"SOURCE_URL: (.*)", header_raw)
    status = extract_meta(r"STATUS: (.*)", header_raw)
    effective_date = extract_meta(r"EFFECTIVE_DATE: (.*)", header_raw)
    signed_date = extract_meta(r"SIGNED_DATE: (.*)", header_raw)
    
    # Ép kiểu filter_year về INT để Vector DB có thể lọc range (ví dụ: > 1945)
    filter_year_raw = extract_meta(r"FILTER_YEAR: (.*)", header_raw, "0")
    try:
        filter_year = int(filter_year_raw)
    except:
        filter_year = 0

    metadata = {
        "id": item_id,
        "title": title,
        "url": url,
        "status": status,
        "effective_date": effective_date,
        "signed_date": signed_date,
        "filter_year": filter_year
    }
    
    # Nhãn hiển thị cho LLM (có thêm năm và trạng thái để AI "biết thân biết phận")
    source_label = (
        f"--- 📚 NGUỒN DỮ LIỆU LUẬT VIỆT NAM ---\n"
        f"📄 TIÊU ĐỀ: {title}\n"
        f"🆔 ID: {item_id} | 📅 NĂM: {filter_year} | 🚦 TRẠNG THÁI: {status}\n"
        f"🔗 URL: {url}\n"
        f"--------------------------------------\n"
    )

    # --- LOGIC TÁCH CHUNK (Giữ nguyên sự bá đạo của bản v15) ---
    body = re.sub(r'(Điều(?:\s+thứ|\s+số)?|Chương)[\s\n]+([IVXLCDM\d]+\.?)', r'\1 \2', raw_body, flags=re.IGNORECASE)
    body = re.sub(r'[ \t]+', ' ', body)

    chapter_blocks = re.split(r'\n(?=Chương\s+[IVXLCDM\d]+)', body, flags=re.IGNORECASE)
    final_chunks = []
    current_chapter = "PHẦN MỞ ĐẦU / CĂN CỨ"

    for chapter_block in chapter_blocks:
        chapter_block = chapter_block.strip()
        if not chapter_block: continue

        chapter_match = re.match(r'^(Chương\s+[IVXLCDM\d]+.*?)\n', chapter_block, flags=re.IGNORECASE)
        if chapter_match:
            current_chapter = chapter_match.group(1).strip().upper()

        temp_splits = re.split(r'\n(?=Điều(?:\s+thứ|\s+số)?\s+\d+)', chapter_block, flags=re.IGNORECASE)
        
        combined_articles = []
        for split in temp_splits:
            if not combined_articles:
                combined_articles.append(split)
            else:
                lines = combined_articles[-1].strip().split('\n')
                last_line = lines[-1] if lines else ""
                if re.search(r'\d+\.\s*$', last_line):
                    combined_articles[-1] = combined_articles[-1] + "\n" + split
                else:
                    combined_articles.append(split)

        for art_block in combined_articles:
            art_block = art_block.strip()
            if not art_block: continue

            # Xử lý nội dung căn cứ đầu trang hoặc lời dẫn
            if not re.match(r'^Điều(?:\s+thứ|\s+số)?', art_block, flags=re.IGNORECASE):
                final_chunks.append({
                    "location": current_chapter,
                    "content": f"{source_label}📍 VỊ TRÍ: {current_chapter}\n{art_block}",
                    "metadata": metadata
                })
                continue

            # Logic tách Khoản (Điểm số)
            point_pattern = re.compile(r'\n\s*(\d+)\.(?:\s|\n|$)')
            matches = list(point_pattern.finditer(art_block))
            
            valid_split_indices = []
            for m in matches:
                start_idx = m.start()
                following_text = art_block[start_idx:start_idx+150].lower()
                prefix = art_block[:start_idx]
                quote_count = prefix.count('"') + prefix.count('“') + prefix.count('”')
                
                if quote_count % 2 == 0:
                    amending_keywords = r'(điều(?:\s+thứ|\s+số)?|khoản|điểm|chương|mục)\s+\d+|sửa đổi|bổ sung'
                    if re.search(amending_keywords, following_text):
                        valid_split_indices.append(start_idx)

            if valid_split_indices:
                first_split = valid_split_indices[0]
                parent_anchor = art_block[:first_split].strip()
                
                for i in range(len(valid_split_indices)):
                    start = valid_split_indices[i]
                    end = valid_split_indices[i+1] if i+1 < len(valid_split_indices) else len(art_block)
                    point_content = art_block[start:end].strip()
                    
                    final_chunks.append({
                        "location": current_chapter,
                        "anchor": parent_anchor,
                        "content": f"{source_label}📍 VỊ TRÍ: {current_chapter}\n👉 ⚖️ CĂN CỨ GỐC: {parent_anchor}\n\n📝 NỘI DUNG CHI TIẾT:\n{point_content}",
                        "metadata": metadata
                    })
            else:
                final_chunks.append({
                    "location": current_chapter,
                    "content": f"{source_label}📍 VỊ TRÍ: {current_chapter}\n{art_block}",
                    "metadata": metadata
                })

    return final_chunks

def process_all_files():
    if not os.path.exists(CONTENTS_OUTPUT_DIR):
        print(f"❌ Thư mục nguồn không tồn tại: {CONTENTS_OUTPUT_DIR}")
        return

    os.makedirs(JSON_CHUNKS_DIR, exist_ok=True)
    print(f"🚀 Bắt đầu xử lý Metadata từ: {CONTENTS_OUTPUT_DIR}")
    
    for root, dirs, files in os.walk(CONTENTS_OUTPUT_DIR):
        for file in files:
            if file.endswith(".txt"):
                input_file_path = os.path.join(root, file)
                
                # Tạo thư mục con tương ứng trong processed/json_chunks
                relative_path = os.path.relpath(root, CONTENTS_OUTPUT_DIR)
                target_output_dir = os.path.join(JSON_CHUNKS_DIR, relative_path)
                os.makedirs(target_output_dir, exist_ok=True)
                
                output_file_name = file.replace(".txt", ".json")
                output_file_path = os.path.join(target_output_dir, output_file_name)
                
                print(f"📄 Đang bóc tách: {relative_path}/{file}")
                
                try:
                    with open(input_file_path, 'r', encoding='utf-8') as f:
                        data = f.read()
                    
                    chunks = legal_pro_rag_splitter_v16(data)
                    
                    output_data = {
                        "filename": file,
                        "agency": relative_path,
                        "total_chunks": len(chunks),
                        "chunks": chunks
                    }
                    
                    with open(output_file_path, 'w', encoding='utf-8') as f:
                        json.dump(output_data, f, ensure_ascii=False, indent=4)
                        
                except Exception as e:
                    print(f"❌ Lỗi tại file {file}: {e}")

    print(f"\n✅ HOÀN TẤT! Dữ liệu JSON đã sẵn sàng cho Vector DB tại: {JSON_CHUNKS_DIR}")

if __name__ == "__main__":
    process_all_files()