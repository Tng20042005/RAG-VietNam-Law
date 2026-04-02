from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from fastapi.responses import StreamingResponse


# from src.engine.rag_engine import VietnamLawEngine
from src.engine.rag_engine import VietnamLawLangChainEngine

app = FastAPI(title="Vietnam Law AI API")

# Create Rag_Enginee
print("🚀 Đang khởi động RAG Engine...")
engine = VietnamLawLangChainEngine()

class QueryRequest(BaseModel):
    prompt: str
    history: list = []

@app.post("/ask")
async def ask_lawyer(request: QueryRequest):
    # Trả về một luồng dữ liệu (generator)
    return StreamingResponse(
        engine.ask_stream(request.prompt, request.history), 
        media_type="text/plain"
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)