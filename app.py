import os
import json
import io
import streamlit as st
import pandas as pd
from openai import OpenAI
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Настройка страницы
st.set_page_config(page_title="Kobi — Коммерческий AI Агент", page_icon="🤖", layout="wide")

st.title("🤖 Kobi — Автономный Коммерческий Агент")
st.caption("Профессиональный мультимодельный ассистент для бизнеса.")

# ЖЕСТКО ЗАШИТЫЙ КЛЮЧ ИЗ ОБЛАЧНЫХ СЕКРЕТОВ
MASTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

with st.sidebar:
    st.header("⚙️ Панель управления")
    model_choice = st.selectbox(
        "Выбор модели", 
        ["deepseek/deepseek-chat", "anthropic/claude-3.5-sonnet", "openai/gpt-4o-mini"]
    )
    st.markdown("---")
    st.success("✅ Система подключена и готова к работе.")

# Функция создания PDF-документа
def generate_pdf_report(title, content):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Заголовок
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, title)
    
    # Текст отчета
    c.setFont("Helvetica", 12)
    text_y = height - 90
    for line in content.split('\n'):
        if text_y < 50:  # Перенос на новую страницу, если текст длинный
            c.showPage()
            c.setFont("Helvetica", 12)
            text_y = height - 50
        c.drawString(50, text_y, line)
        text_y -= 20
        
    c.save()
    buffer.seek(0)
    return buffer

# Инициализация истории чата
if "messages" not in st.session_state:
    st.session_state.messages = []

# Вывод истории сообщений
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "file_path" in message and os.path.exists(message["file_path"]):
            with open(message["file_path"], "rb") as f:
                file_name = os.path.basename(message['file_path'])
                mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_name.endswith(".xlsx") else "application/pdf"
                st.download_button(
                    label=f"📥 Скачать файл: {file_name}",
                    data=f,
                    file_name=file_name,
                    mime=mime_type,
                    key=f"hist_{message['file_path']}_{os.path.getmtime(message['file_path'])}"
                )

# Обработка ввода пользователя
if prompt := st.chat_input("Какую задачу нужно решить? (например: 'Сделай смету' или 'Напиши КП в PDF')"):
    if not MASTER_API_KEY or MASTER_API_KEY.startswith("sk-or-v1-..."):
        st.error("Пожалуйста, укажи свой реальный OpenRouter API-ключ.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Kobi анализирует задачу и формирует структуру...", expanded=True) as status:
            
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=MASTER_API_KEY,
            )
            
            system_prompt = (
                "Ты — автономный коммерческий агент Kobi. Твоя задача — решать бизнес-задачи.\n"
                "Выбирай один из навыков в начале ответа:\n"
                "1. [EXCEL] — если пользователь просит таблицу, смету, расчеты. В конце ответа добавь блок данных в формате JSON строго по шаблону:\n"
                "```json\n"
                "{\n"
                '  "columns": ["Колонка 1", "Колонка 2", "Колонка 3"],\n'
                '  "rows": [\n'
                '    ["Значение 1", "Значение 2", "Значение 3"]\n'
                "  ]\n"
                "}\n"
                "```\n"
                "2. [PDF] — если пользователь просит коммерческое предложение, договор, текстовый отчет или документ для скачивания.\n"
                "3. [TEXT] — если файлы не нужны, просто отвечай на вопрос без блоков.\n"
                "НИКОГДА не выводи исходный код Python в чат."
            )
            
            messages = [{"role": "system", "content": system_prompt}] + [
                {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
            ]
            
            response = client.chat.completions.create(
                model=model_choice,
                messages=messages
            )
            full_reply = response.choices[0].message.content
            
            skill_tag = "[TEXT]"
            reply_text = full_reply
            excel_data = None
            
            if "[EXCEL]" in full_reply:
                skill_tag = "[EXCEL]"
                parts = full_reply.split("```json")
                reply_text = parts[0].replace("[EXCEL]", "").strip()
                if len(parts) > 1:
                    try:
                        json_str = parts[1].split("
