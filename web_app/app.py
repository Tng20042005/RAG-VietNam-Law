import streamlit as st
import requests
import json
from fpdf import FPDF
import io
import os
from fpdf.enums import XPos, YPos

st.set_page_config(page_title="Luật Sư AI Việt Nam", page_icon="⚖️")

# --- 1. HÀM TẠO PDF (CẬP NHẬT DEBUG) ---
def export_single_to_pdf(question, answer, sources):
    pdf = FPDF()
    pdf.add_page()
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(current_dir, "assets", "fonts", "DejaVuSans.ttf")

    # KIỂM TRA FONT
    if os.path.exists(font_path):
        pdf.add_font('DejaVu', '', font_path)
        pdf.set_font('DejaVu', '', 12)
    else:
        # TRƯỜNG HỢP THIẾU FONT: Dùng font tạm để nút VẪN HIỆN LÊN
        pdf.set_font('Arial', '', 12)
        # Ghi chú nhỏ vào PDF để biết đang thiếu font
        pdf.write(10, "LƯU Ý: THIẾU FONT TIẾNG VIỆT (DEJAVU)\n")

    # Tiêu đề
    pdf.cell(200, 10, text="BÁO CÁO TƯ VẤN PHÁP LUẬT", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
    pdf.ln(10)

    # Nội dung (Dùng multi_cell để tránh lỗi tràn dòng)
    pdf.write(10, "Câu hỏi:\n")
    pdf.multi_cell(0, 8, text=question)
    pdf.ln(5)
    pdf.write(10, "Tư vấn:\n")
    pdf.multi_cell(0, 8, text=answer)
    
    return pdf.output()

# --- 2. THANH BÊN ---
with st.sidebar:
    st.title("⚙️ Tùy chọn")
    # Kiểm tra font và báo lỗi ở sidebar cho bạn thấy
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_check = os.path.join(current_dir, "assets", "fonts", "DejaVuSans.ttf")
    if not os.path.exists(font_check):
        st.error(f"⚠️ Thiếu file font tại: {font_check}")
        st.caption("Hãy chạy lệnh copy font trong terminal!")
    
    if st.button("🗑️ Xóa lịch sử trò chuyện", use_container_width=True, key="clear_chat_btn"):
        st.session_state.messages = []
        st.rerun()

# --- 3. GIAO DIỆN CHÍNH ---
st.title("⚖️ Trợ Lý Luật Sư AI")

if "messages" not in st.session_state:
    st.session_state.messages = []

# HIỂN THỊ LỊCH SỬ
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        if message["role"] == "assistant":
            if message.get("sources"):
                with st.expander("📚 Xem lại căn cứ pháp lý"):
                    for src in message["sources"]:
                        st.markdown(f"**{src['title']}**")
                        if "content" in src: st.info(src["content"])
            
            # --- NÚT DOWNLOAD LUÔN LUÔN ĐƯỢC GỌI ---
            user_q = st.session_state.messages[i-1]["content"] if i > 0 else "Câu hỏi"
            
            try:
                pdf_out = export_single_to_pdf(user_q, message["content"], message.get("sources", []))
                st.download_button(
                    label="📥 Tải đoạn tư vấn này (PDF)",
                    data=bytes(pdf_out),
                    file_name=f"tu_van_le_{i}.pdf",
                    mime="application/pdf",
                    key=f"dl_{i}"
                )
            except Exception as e:
                st.error(f"Lỗi tạo PDF: {e}")

# XỬ LÝ NHẬP LIỆU MỚI
if prompt := st.chat_input("Bạn muốn hỏi gì về luật?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        res_state = {"full_response": "", "sources": []}
        payload = {"prompt": prompt, "history": st.session_state.messages[:-1]}

        try:
            with requests.post("http://localhost:8000/ask", json=payload, stream=True) as r:
                def stream_display():
                    for line in r.iter_lines(decode_unicode=True):
                        if not line: continue
                        if line.startswith("__SOURCES__:"):
                            try:
                                clean_json = line.replace("__SOURCES__:", "").strip()
                                res_state["sources"] = json.loads(clean_json)
                            except: pass
                            continue
                        res_state["full_response"] += line + "\n"
                        yield line + "\n"
                st.write_stream(stream_display())

            st.session_state.messages.append({
                "role": "assistant", 
                "content": res_state["full_response"],
                "sources": res_state["sources"]
            })
            # BUỘC RERUN ĐỂ NÚT HIỆN RA
            st.rerun()

        except Exception as e:
            st.error(f"Lỗi kết nối Backend: {e}")