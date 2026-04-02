import os
import json
import re
from neo4j import GraphDatabase
from dotenv import load_dotenv
import glob

load_dotenv()

JSON_CHUNKS_DIR = os.getenv("JSON_CHUNKS_DIR", "/home/gnut_2004/Project/Rag/vietnam_law/data/processed/json_chunks")

class LegalGraphBuilder:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            "bolt://localhost:7687", 
            auth=("neo4j", "password123")
        )
        # Bộ từ điển nhận diện loại văn bản từ số hiệu (Dự phòng)
        self.suffix_map = {
            "nđ-cp": "Nghị định", "tt-": "Thông tư", "qh": "Luật", 
            "sl": "Sắc lệnh", "qđ-": "Quyết định", "ct-": "Chỉ thị", "nq-": "Nghị quyết"
        }

    def close(self):
        self.driver.close()

    def get_document_type(self, content):
        """Ưu tiên bắt chữ IN HOA ở đầu dòng để phân loại"""
        lines = content.split('\n')
        for line in lines[:15]: # Quét 15 dòng đầu của chunk mở đầu
            clean_line = line.strip().upper()
            for loai in ["LUẬT", "BỘ LUẬT", "NGHỊ ĐỊNH", "THÔNG TƯ", "QUYẾT ĐỊNH", "SẮC LỆNH", "CHỈ THỊ"]:
                if clean_line.startswith(loai):
                    return loai.capitalize()
        return "Văn bản"

    def create_graph_from_json(self, json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        with self.driver.session() as session:
            # 1. Lấy thông tin chung của Văn bản từ Metadata chunk đầu tiên
            main_meta = data["chunks"][0]["metadata"]
            doc_type = self.get_document_type(data["chunks"][0]["content"])
            doc_name = f"{doc_type} {main_meta['id']} ({main_meta['filter_year']})"
            
            # Tạo Node gốc: Văn bản Luật
            session.run("""
                MERGE (v:VanBanLuat {id: $id})
                SET v.name = $name, v.type = $type, v.year = $year, v.status = $status, v.url = $url
            """, id=main_meta['id'], name=doc_name, type=doc_type, 
                 year=main_meta['filter_year'], status=main_meta['status'], url=main_meta['url'])

            # 2. Lặp qua từng Chunk để tạo Node Điều Khoản và Nội Dung
            for idx, chunk in enumerate(data["chunks"]):
                content = chunk["content"]
                
                # Tìm xem chunk này có chứa "Điều X" không
                dieu_match = re.search(r"^(Điều(?: thứ)? \d+)", content, re.MULTILINE | re.IGNORECASE)
                
                if dieu_match:
                    dieu_label = dieu_match.group(1)
                    dieu_id = f"{main_meta['id']}_{dieu_label.replace(' ', '_')}"
                    
                    # Tạo Node Điều Khoản
                    session.run("""
                        MATCH (v:VanBanLuat {id: $doc_id})
                        MERGE (d:DieuKhoan {id: $dieu_id})
                        SET d.label = $label
                        MERGE (d)-[:THUOC_VE]->(v)
                    """, doc_id=main_meta['id'], dieu_id=dieu_id, label=dieu_label)

                    # Tạo Node NoiDung (Chunk thật) nối vào Điều Khoản
                    session.run("""
                        MATCH (d:DieuKhoan {id: $dieu_id})
                        CREATE (c:NoiDung {id: $chunk_id})
                        SET c.text = $text, c.location = $loc
                        CREATE (d)-[:CO_NOI_DUNG]->(c)
                    """, dieu_id=dieu_id, chunk_id=f"{dieu_id}_{idx}", text=content, loc=chunk["location"])
                
                else:
                    # Nếu là phần mở đầu/căn cứ không có Điều, nối thẳng vào Văn bản gốc
                    session.run("""
                        MATCH (v:VanBanLuat {id: $doc_id})
                        CREATE (c:NoiDung {id: $chunk_id})
                        SET c.text = $text, c.location = $loc
                        CREATE (v)-[:CO_NOI_DUNG]->(c)
                    """, doc_id=main_meta['id'], chunk_id=f"base_{main_meta['id']}_{idx}", text=content, loc=chunk["location"])

        print(f"✅ Đã nạp xong đồ thị cho: {doc_name}")

if __name__ == "__main__":
    builder = LegalGraphBuilder()
    print("Bắt đầu tạo Knowleadge Graph",JSON_CHUNKS_DIR)
    
    count = 0
    for root, dirs, files in os.walk(JSON_CHUNKS_DIR):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                department = os.path.basename(root)

                try:
                    print(f"Đang nạp dữ liệu {department} - {file}")
                    builder.create_graph_from_json(file_path)
                    count +=1
                
                except Exception as e:
                    print(f'Lỗi tại file: {file_path}: e')
    print(f"Hoàn thành, đã nạp tổng cộng {count} files vào graph")
    builder.close()