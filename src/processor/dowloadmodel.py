
# import os
# from huggingface_hub import snapshot_download

# MODEL_ID = "jinaai/jina-reranker-v2-base-multilingual"
# SAVE_PATH = "/home/gnut_2004/Project/Rag/vietnam_law/data/models/reranker/jina-reranker-v2-base-multilingual"

# def download_jina_clean():
#     print(f"🚚 Đang tải 'trắng' model {MODEL_ID}...")
    
#     try:
#         snapshot_download(
#             repo_id=MODEL_ID,
#             local_dir=SAVE_PATH,
#             local_dir_use_symlinks=False, # Copy file thật, không dùng link ảo
#             revision="main"
#         )
#         print(f"✅ Xong rồi! Model đã nằm gọn trong: {SAVE_PATH}")
        
#     except Exception as e:
#         print(f"❌ Lỗi khi tải: {e}")

# if __name__ == "__main__":
#     download_jina_clean()
from huggingface_hub import snapshot_download
import os

local_dir = "/home/gnut_2004/Project/Rag/vietnam_law/data/models/LLM/qwen2.5-1.5b-instruct"

print(f"🚀 Đang tải Qwen2.5-1.5B về: {local_dir}...")

snapshot_download(
    repo_id="Qwen/Qwen2.5-1.5B-Instruct",
    local_dir=local_dir,
    local_dir_use_symlinks=False,
    revision="main"
)

print("✅ Đã tải xong! Giờ bạn có thể ngắt mạng và chạy Offline.")