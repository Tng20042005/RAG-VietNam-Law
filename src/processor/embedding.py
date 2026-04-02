import os
import json
import torch
import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

JSON_ROOT_DIR = os.getenv("JSON_CHUNKS_DIR")
DB_PATH = os.getenv("DB_PATH")
LOCAL_MODEL_PATH = os.getenv("LOCAL_MODEL_PATH")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

# Check existing ids
def get_existing_ids(collection):
    """Lấy danh sách ID đã tồn tại trong DB để tránh embedding lại"""
    results = collection.get(include=[])
    return set(results['ids'])
    
# Create Indexing
def run_indexing():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    
    print("🔍 Đang kiểm tra dữ liệu cũ trong Database...")
    indexed_ids = get_existing_ids(collection)
    print(f"✅ Đã tìm thấy {len(indexed_ids)} mảnh luật trong DB.")

    model = None 
    new_chunks_total = 0
    
    for root, dirs, files in os.walk(JSON_ROOT_DIR):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                chunks = data.get("chunks", [])
                if not chunks: continue

                # Sử dụng key 'id' đồng bộ với process.py
                doc_id = chunks[0]['metadata'].get('id', 'unknown')
                first_chunk_id = f"{doc_id}_chunk_0"
                
                if first_chunk_id in indexed_ids:
                    # print(f"⏭️ Bỏ qua: {file} (Đã tồn tại)")
                    continue

                if model is None:
                    print(f"🧠 Đang nạp model E5 lên {device.upper()}...")
                    model = SentenceTransformer(LOCAL_MODEL_PATH).to(device)

                try:
                    # E5 cần tiền tố "passage: " để đạt hiệu quả tốt nhất khi index
                    documents = [c['content'] if c['content'].startswith("passage:") else f"passage: {c['content']}" for c in chunks]
                    
                    # Đảm bảo Metadata sạch để ChromaDB không báo lỗi
                    metadatas = []
                    for c in chunks:
                        m = c["metadata"]
                        # Đảm bảo các giá trị N/A không bị None
                        clean_meta = {k: (v if v is not None else "N/A") for k, v in m.items()}
                        metadatas.append(clean_meta)

                    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]

                    embeddings = model.encode(
                        documents, 
                        batch_size=32, 
                        show_progress_bar=False, 
                        convert_to_numpy=True
                    ).tolist()

                    collection.add( 
                        embeddings=embeddings,
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids
                    )
                    
                    new_chunks_total += len(chunks)
                    print(f"✨ Đã nạp mới: {file} ({len(chunks)} chunks) | ID: {doc_id}")

                except Exception as e:
                    print(f"🔥 Lỗi tại file {file}: {e}")

    if new_chunks_total > 0:
        print(f"\n🏆 HOÀN THÀNH! Đã nạp thêm {new_chunks_total} mảnh luật mới.")
    else:
        print("\n☕ Không có dữ liệu gì mới để nạp. Nghỉ ngơi thôi!")

if __name__ == "__main__":
    run_indexing()