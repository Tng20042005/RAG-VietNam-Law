
import os
import json
from dotenv import load_dotenv

# LangChain Core & Google
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage

# Thêm 3 dòng này vào khu vực import ở đầu file
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_core.prompts import PromptTemplate

# VectorStore & Embeddings
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# Reranker (Giữ nguyên CrossEncoder nhưng bọc vào LangChain)
from sentence_transformers import CrossEncoder

load_dotenv()

class VietnamLawLangChainEngine:
    def __init__(self):
        # 1. Khởi tạo Gemini LLM
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0
        )

        # 2. Khởi tạo Embedding (E5)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=os.getenv("LOCAL_MODEL_PATH"),
            model_kwargs={'device': 'cuda'}
        )

        # 3. Kết nối ChromaDB
        self.vector_store = Chroma(
            persist_directory=os.getenv("DB_PATH"),
            embedding_function=self.embeddings,
            collection_name=os.getenv("COLLECTION_NAME")
        )

        # 4. Jina Reranker v2
        self.reranker = CrossEncoder(
            os.getenv("JINA_LOCAL_PATH"),
            device="cuda",
            tokenizer_kwargs={"fix_mistral_regex": True},
            trust_remote_code=True,
            model_kwargs={"dtype": "float16"}
        )

        self.graph = Neo4jGraph(
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    # Tinh chỉnh Prompt một chút để Gemini viết Cypher chuẩn hơn
        # Đã thêm biến {schema} để LangChain tự quét cấu trúc DB của bạn
        # Tinh chỉnh Prompt: Thêm ví dụ mẫu (Few-shot) để Gemini bắt chước 100%
        # Prompt mới: Cấm tìm theo tên Luật, chuyển sang tìm theo Từ Khóa trong Nội dung (NoiDung.text)
        cypher_template = """
        Task: Generate a Cypher query to answer the Vietnamese law question.
        
        Graph Schema Provided by Neo4j:
        {schema}
        
        CRITICAL RULES (MUST FOLLOW):
        1. WARNING: The 'name' property of VanBanLuat currently contains ID numbers, NOT real names. DO NOT USE `v.name` FOR SEARCHING!
        2. To find a specific Article (Điều), filter by Article ID (`d.id CONTAINS 'Điều_X'`) AND search for keywords inside the content (`n.text`).
        3. ALWAYS use `toLower()` and `CONTAINS` for text search.
        
        EXAMPLES:
        User: "Điều 173 của Bộ luật Hình sự quy định về tội trộm cắp thế nào?"
        Cypher Query: MATCH (d:DieuKhoan)-[:CO_NOI_DUNG]->(n:NoiDung) WHERE d.id CONTAINS 'Điều_173' AND (toLower(n.text) CONTAINS toLower('trộm cắp') OR toLower(n.text) CONTAINS toLower('hình sự')) RETURN d.id, n.text LIMIT 3
        
        User: "Hành vi trộm cắp tài sản bị phạt thế nào?"
        Cypher Query: MATCH (h:Hanhvi)-[:BI_PHAT]->(m:Mucphat) WHERE toLower(h.id) CONTAINS toLower('trộm cắp') RETURN h.id, m.id LIMIT 3
        
        Question: {question}
        Cypher Query:"""
        
        self.cypher_prompt = PromptTemplate(
            input_variables=["schema", "question"], 
            template=cypher_template
        )
        
        # Dùng chính self.llm (Gemini) ở đây
        self.graph_chain = GraphCypherQAChain.from_llm(
            llm=self.llm, 
            graph=self.graph,
            verbose=True,
            cypher_prompt=self.cypher_prompt,
            allow_dangerous_requests=True,
            return_direct=True
        )
    

    # --- BƯỚC 1: PHÂN TÍCH Ý ĐỊNH (Intent Chain) ---

    def get_intent_chain(self):
        prompt = ChatPromptTemplate.from_template("""
Bạn là chuyên gia phân tích pháp luật. Hãy chuyển câu hỏi sau thành JSON điều khiển.

LỊCH SỬ TRÒ CHUYỆN: {history}
CÂU HỎI MỚI: {query}

YÊU CẦU JSON:
1. "rewritten_query": Viết lại câu hỏi đầy đủ, rõ ràng dựa trên lịch sử để có thể tìm kiếm độc lập.
2. "source_years": Danh sách NĂM BAN HÀNH văn bản nhắc tới (VD: 'Luật 2013' -> [2013]). Nếu không nhắc năm cụ thể, để [].
3. "target_year": Năm mà người dùng muốn kiểm tra hiệu lực (Mặc định là 2026).
4. "is_status_check": true nếu người dùng hỏi về việc văn bản còn dùng được không/hết hiệu lực chưa.
5. "is_legal_query": Bắt buộc trả về True nếu câu hỏi liên quan đến pháp luật. Trả về False nếu ngoài luồng.
6. "use_graph": BẮT BUỘC trả về true nếu câu hỏi thuộc các dạng: hỏi số lượng (có bao nhiêu điều/chương), hỏi cấu trúc, hỏi danh sách, hoặc yêu cầu trích xuất chính xác MỘT ĐIỀU LUẬT CỤ THỂ (VD: Điều 173 nói về gì?). Các trường hợp tư vấn tình huống thì trả về false.

CHỈ TRẢ RA JSON, KHÔNG GIẢI THÍCH.
        """)
        return prompt | self.llm | JsonOutputParser()



    # --- BƯỚC 2: RERANKER (Hàm bổ trợ cho LangChain) ---
    def rerank_logic(self, input_data):
        query = input_data["query"]
        docs = input_data["docs"]
        if not docs: return "", []

        passages = [d.page_content for d in docs]
        # Thực hiện rerank bằng Jina
        results = self.reranker.rank(query, passages, top_k=3)
        
        context = ""
        sources = []
        for res in results:
            doc = docs[res['corpus_id']]
            m = doc.metadata
            info = f"[ID: {m.get('id')} | NĂM: {m.get('filter_year')} | TRẠNG THÁI: {m.get('status')}]"
            context += f"\n{info}\n{doc.page_content}\n"
            
            sources.append({
                "title": f"{m.get('title')} ({m.get('filter_year')})",
                "status": m.get('status'),
                "url": m.get("url")
            })
        return context, sources

    # --- BƯỚC 3: XỬ LÝ LỊCH SỬ (Format History) ---
    def format_history(self, history_list):
        if not history_list: return "Không có"
        formatted = ""
        for msg in history_list[-3:]: # Lấy 3 câu gần nhất
            role = "Người dùng" if msg['role'] == 'user' else "AI"
            formatted += f"{role}: {msg['content']}\n"
        return formatted

    # --- BƯỚC 4: MAIN RAG FLOW ---
    def ask_stream(self, query: str, history: list = []):
        # A. Chạy Intent Chain để bóc tách thông tin
        history_str = self.format_history(history)
        intent_chain = self.get_intent_chain()
        intent = intent_chain.invoke({"query": query, "history": history_str})

        if intent.get("use_graph") is True:
            yield "🔍 **[Chế độ Graph]** Đang truy vấn cấu trúc dữ liệu pháp luật...\n\n"
            try:
                # 1. Gọi Graph Chain
                graph_res = self.graph_chain.invoke({"query": intent["rewritten_query"]})
                
                # 2. Lấy dữ liệu ra (Lưu ý: return_direct=True thì kết quả thường nằm trực tiếp ở graph_res)
                # Nếu graph_res là dictionary thì lấy ["result"], nếu không thì lấy chính nó
                data = graph_res.get("result") if isinstance(graph_res, dict) else graph_res

                # 3. XỬ LÝ LỖI 'LIST': Biến danh sách thành chuỗi văn bản
                if isinstance(data, list):
                    if not data:
                        yield "Không tìm thấy thông tin phù hợp trong sơ đồ luật."
                    else:
                        readable_text = ""
                        for record in data:
                            # Ưu tiên lấy cột 'n.text' (Nội dung luật) mà chúng ta đã RETURN trong Cypher
                            content = record.get('n.text', str(record))
                            readable_text += f"{content}\n\n"
                        yield readable_text
                else:
                    # Nếu nó là chuỗi (String) rồi thì cứ thế yield thôi
                    yield str(data)

                return 
            except Exception as e:
                yield f"⚠️ *Lỗi truy vấn Graph: {str(e)}... Đang chuyển sang tìm kiếm chuyên sâu...*\n\n"

            
        if intent.get("is_legal_query") is False:
            yield "Xin lỗi bạn, với vai trò là một trợ lý tư vấn pháp luật Việt Nam, tôi chỉ có thể giải đáp các vấn đề liên quan đến quy định nhà nước, thủ tục pháp lý và luật pháp. Tôi không thể hỗ trợ bạn các vấn đề ngoài luồng như nấu ăn, giải trí hay đời sống thường ngày được."
            return 

        # B. Chuẩn bị Retriever với Metadata Filter (nếu có)
        source_years = [y for y in intent.get("source_years", []) if y < 2026]
        search_kwargs = {"k": 15}
        if source_years:
            if len(source_years) > 1:
                search_kwargs["filter"] = {"filter_year": {"$in": source_years}}
            else:
                search_kwargs["filter"] = {"filter_year": source_years[0]}
        
        retriever = self.vector_store.as_retriever(search_kwargs=search_kwargs)

        # C. Thực hiện Retrieval và Rerank
        raw_docs = retriever.invoke(intent["rewritten_query"])
        context, sources = self.rerank_logic({
            "query": intent["rewritten_query"], 
            "docs": raw_docs
        })

        if not context:
            yield "Xin lỗi, tôi không tìm thấy căn cứ pháp lý nào phù hợp."
            return

        # D. Trả về thông tin nguồn (Sources) trước khi stream
        yield f"__SOURCES__:{json.dumps(sources, ensure_ascii=False)}\n\n"

        # E. Final Chain (Tư vấn luật)
        rag_prompt = ChatPromptTemplate.from_template("""
Bạn là Luật sư Việt Nam. Hiện tại là năm {target_year}.
Nhiệm vụ của bạn là giải đáp CÂU HỎI HIỆN TẠI DỰA HOÀN TOÀN VÀO CĂN CỨ PHÁP LÝ được cung cấp dưới đây.

LỊCH SỬ TRÒ CHUYỆN:
{history}

CĂN CỨ PHÁP LÝ:
{context}

CÂU HỎI HIỆN TẠI: {question}

YÊU CẦU BẮT BUỘC (TUÂN THỦ TUYỆT ĐỐI):
1. CHỈ ĐƯỢC PHÉP trả lời dựa trên thông tin có trong CĂN CỨ PHÁP LÝ. 
2. TUYỆT ĐỐI KHÔNG sử dụng kiến thức bên ngoài, không tự bịa thêm điều luật, không suy diễn nếu tài liệu không đề cập.
3. NẾU CĂN CỨ PHÁP LÝ KHÔNG CHỨA THÔNG TIN ĐỂ TRẢ LỜI CÂU HỎI, bạn PHẢI từ chối trả lời theo mẫu: "Dựa trên cơ sở dữ liệu hiện tại, tôi không tìm thấy văn bản pháp lý nào quy định chính xác về vấn đề này." KHÔNG ĐƯỢC CỐ GẮNG TRẢ LỜI.
4. Nếu TRẠNG THÁI trong căn cứ là 'Hết hiệu lực toàn bộ', phải thông báo rõ văn bản này không còn áp dụng vào năm {target_year}.
5. Trích dẫn chính xác Số văn bản, Điều, Khoản từ căn cứ được cung cấp.
        """)

        final_chain = rag_prompt | self.llm | StrOutputParser()

        # F. Stream kết quả
        for chunk in final_chain.stream({
            "context": context,
            "question": query,
            "history": history_str,
            "target_year": intent.get("target_year", 2026)
        }):
            yield chunk






################ Not Depend on API Key of Geimini######################33

# import os
# import json
# import re
# from threading import Thread
# from dotenv import load_dotenv

# import torch
# from transformers import (
#     AutoModelForCausalLM, 
#     AutoTokenizer, 
#     BitsAndBytesConfig, 
#     TextIteratorStreamer
# )

# # LangChain Core
# from langchain_core.prompts import ChatPromptTemplate

# # VectorStore & Embeddings
# from langchain_chroma import Chroma
# from langchain_huggingface import HuggingFaceEmbeddings

# # Reranker (Giữ nguyên)
# from sentence_transformers import CrossEncoder

# load_dotenv()

# class VietnamLawQwenEngine:
#     def __init__(self):
#         print(">>> [Hệ thống] Đang khởi tạo Qwen Local & LangChain RAG...")

#         # 1. Khởi tạo Qwen Local với nén 4-bit (Tối ưu VRAM)
#         self.llm_path = os.getenv("LLM_LOCAL_PATH", "Qwen/Qwen2.5-1.5B-Instruct")
#         bnb_config = BitsAndBytesConfig(
#             load_in_4bit=True,
#             bnb_4bit_compute_dtype=torch.float16,
#             bnb_4bit_quant_type="nf4",
#             bnb_4bit_use_double_quant=True
#         )
        
#         self.tokenizer = AutoTokenizer.from_pretrained(self.llm_path)
#         self.llm_model = AutoModelForCausalLM.from_pretrained(
#             self.llm_path,
#             quantization_config=bnb_config,
#             device_map="auto",
#             trust_remote_code=True
#         )

#         # 2. Khởi tạo Embedding (E5) qua LangChain
#         self.embeddings = HuggingFaceEmbeddings(
#             model_name=os.getenv("LOCAL_MODEL_PATH", "intfloat/multilingual-e5-small"),
#             model_kwargs={'device': 'cuda'}
#         )

#         # 3. Kết nối ChromaDB qua LangChain
#         self.vector_store = Chroma(
#             persist_directory=os.getenv("DB_PATH"),
#             embedding_function=self.embeddings,
#             collection_name=os.getenv("COLLECTION_NAME")
#         )

#         # 4. Jina Reranker v2 (Chạy float16)
#         self.reranker = CrossEncoder(
#             os.getenv("JINA_LOCAL_PATH", "jinaai/jina-reranker-v2-base-multilingual"),
#             device="cuda",
#             tokenizer_kwargs={"fix_mistral_regex": True},
#             trust_remote_code=True,
#             model_kwargs={"dtype": torch.float16} 
#         )

#     # --- BƯỚC 1: PHÂN TÍCH Ý ĐỊNH (Tối ưu cho Local) ---
#     def get_intent_local(self, query: str):
#         """
#         Local model nhỏ xuất JSON dễ lỗi. Dùng Regex để tách năm ban hành
#         đảm bảo tốc độ < 0.01s và chính xác 100%.
#         """
#         years = [int(y) for y in re.findall(r'\b(19\d{2}|20\d{2})\b', query)]
#         source_years = [y for y in years if y < 2026]
        
#         # Keyword đơn giản để check xem có phải câu hỏi đời thường không
#         non_legal_keywords = ['nấu ăn', 'thời tiết', 'chơi game', 'phim', 'code', 'python', 'java']
#         is_legal = not any(kw in query.lower() for kw in non_legal_keywords)

#         return {
#             "rewritten_query": query,
#             "source_years": source_years,
#             "target_year": 2026,
#             "is_legal_query": is_legal
#         }

#     # --- BƯỚC 2: RERANKER LOGIC ---
#     def rerank_logic(self, input_data):
#         query = input_data["query"]
#         docs = input_data["docs"]
#         if not docs: return "", []

#         passages = [d.page_content for d in docs]
#         results = self.reranker.rank(query, passages, top_k=3)
        
#         context = ""
#         sources = []
#         for res in results:
#             doc = docs[res['corpus_id']]
#             m = doc.metadata
#             info = f"[ID: {m.get('id')} | NĂM: {m.get('filter_year')} | TRẠNG THÁI: {m.get('status')}]"
#             context += f"\n{info}\n{doc.page_content}\n"
            
#             sources.append({
#                 "title": f"{m.get('title')} ({m.get('filter_year')})",
#                 "status": m.get('status'),
#                 "url": m.get("url")
#             })
#         return context, sources

#     # --- BƯỚC 3: XỬ LÝ LỊCH SỬ ---
#     def format_history(self, history_list):
#         if not history_list: return "Không có"
#         formatted = ""
#         for msg in history_list[-3:]:
#             role = "Người dùng" if msg['role'] == 'user' else "Luật sư"
#             formatted += f"{role}: {msg['content']}\n"
#         return formatted

#     # --- BƯỚC 4: MAIN RAG FLOW (STREAMING QWEN) ---
#     def ask_stream(self, query: str, history: list = []):
#         # A. Chạy Intent Parser
#         history_str = self.format_history(history)
#         intent = self.get_intent_local(query)

#         if not intent.get("is_legal_query"):
#             yield "Xin lỗi bạn, với vai trò là một trợ lý tư vấn pháp luật Việt Nam, tôi chỉ có thể giải đáp các vấn đề liên quan đến quy định nhà nước, thủ tục pháp lý và luật pháp."
#             return 

#         # B. Chuẩn bị Retriever với Metadata Filter
#         source_years = intent.get("source_years", [])
#         search_kwargs = {"k": 15}
#         if source_years:
#             if len(source_years) > 1:
#                 search_kwargs["filter"] = {"filter_year": {"$in": source_years}}
#             else:
#                 search_kwargs["filter"] = {"filter_year": source_years[0]}
        
#         retriever = self.vector_store.as_retriever(search_kwargs=search_kwargs)

#         # C. Thực hiện Retrieval và Rerank
#         raw_docs = retriever.invoke(intent["rewritten_query"])
#         context, sources = self.rerank_logic({
#             "query": intent["rewritten_query"], 
#             "docs": raw_docs
#         })

#         if not context:
#             yield "Dựa trên cơ sở dữ liệu hiện tại, tôi không tìm thấy văn bản pháp lý nào quy định chính xác về vấn đề này."
#             return

#         # D. Trả về thông tin nguồn (Sources)
#         yield f"__SOURCES__:{json.dumps(sources, ensure_ascii=False)}\n\n"

#         # E. Xây dựng Chat Prompt cho Qwen
#         target_year = intent.get("target_year", 2026)
#         system_prompt = (
#             f"Bạn là Luật sư Việt Nam. Hiện tại là năm {target_year}. "
#             "Nhiệm vụ của bạn là giải đáp CÂU HỎI HIỆN TẠI DỰA HOÀN TOÀN VÀO CĂN CỨ PHÁP LÝ được cung cấp.\n"
#             "YÊU CẦU BẮT BUỘC:\n"
#             "1. CHỈ ĐƯỢC PHÉP trả lời dựa trên thông tin có trong CĂN CỨ PHÁP LÝ.\n"
#             "2. TUYỆT ĐỐI KHÔNG tự bịa thêm điều luật.\n"
#             f"3. Nếu trạng thái là 'Hết hiệu lực toàn bộ', phải báo rõ văn bản không còn áp dụng vào năm {target_year}.\n"
#             "4. Trích dẫn chính xác Số văn bản, Điều, Khoản."
#         )
        
#         user_prompt = f"LỊCH SỬ TRÒ CHUYỆN:\n{history_str}\n\nCĂN CỨ PHÁP LÝ:\n{context}\n\nCÂU HỎI HIỆN TẠI: {query}\n\nTRẢ LỜI:"
        
#         messages = [
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt}
#         ]

#         # Template hoá đoạn hội thoại cho Qwen
#         prompt_text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
#         inputs = self.tokenizer([prompt_text], return_tensors="pt").to("cuda")

#         # F. Cấu hình Streaming cho HuggingFace Local Model
#         streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        
#         generation_kwargs = dict(
#             **inputs,
#             streamer=streamer,
#             max_new_tokens=1024,
#             temperature=0.1,  # Nhiệt độ thấp = Ít ảo giác pháp luật
#             do_sample=False,
#             repetition_penalty=1.1
#         )

#         # Chạy model.generate trên luồng phụ để giải phóng luồng chính cho hàm yield
#         thread = Thread(target=self.llm_model.generate, kwargs=generation_kwargs)
#         thread.start()

#         # G. Stream text realtime
#         for new_text in streamer:
#             yield new_text
            
#         thread.join()