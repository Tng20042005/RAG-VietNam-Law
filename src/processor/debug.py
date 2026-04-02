import chromadb
import os
from dotenv import load_dotenv

load_dotenv()
# Kết nối tới DB của bạn
client = chromadb.PersistentClient(path=os.getenv("DB_PATH"))
collection = client.get_collection(name=os.getenv("COLLECTION_NAME"))

# Lấy ra 3 đoạn luật bất kỳ để soi Metadata
sample = collection.get(limit=3)

print("--- KIỂM TRA METADATA ---")
if sample['metadatas']:
    for i, meta in enumerate(sample['metadatas']):
        print(f"Đoạn {i+1}: {meta}")
else:
    print("DB của bạn chưa có Metadata!")