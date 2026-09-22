import os
import json
import io
import re
import streamlit as st
import pandas as pd
from openai import OpenAI
from docx import Document

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

def generate_word_report(title, content):
    doc = Document()
    doc.add_heading(title, level=1)
    
    clean_content = re.sub(r'[*#_`]', '', content)
    for line in clean_content.split('\n'):
        if line.strip():
            doc.add_paragraph(line.strip())
        else:
            doc.add_paragraph() # Пустая строка для отступа
            
    buffer = io.BytesIO()
    doc.save(buffer)
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
                if file_name.endswith(".xlsx"):
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                else:
                    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                
                st.download_button(
                    label=f"📥 Скачать файл: {file_name}",
                    data=f,
                    file_name=file_name,
                    mime=mime_type,
                    key=f"hist_{message['file_path']}_{os.path.getmtime(message['file_path'])}"
                )

# Обработка ввода пользователя
if prompt := st.chat_input("Какую задачу нужно решить? (например: 'Напиши сочинение про природу' или 'Сделай смету')"):
    if not MASTER_API_KEY or MASTER_API_KEY.startswith("sk-or-v1-..."):
        st.error("Пожалуйста, укажи свой реальный OpenRouter API-ключ.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Kobi анализирует задачу и формирует документ...", expanded=True) as status:
            
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=MASTER_API_KEY,
            )
            
            system_prompt = (
                "Ты — автономный коммерческий агент Kobi. Твоя задача — решать бизнес-задачи.\n"
                "СТРОГОЕ ПРАВИЛО: Каждый ответ ты ОБЯЗАН начинать с одного из тегов в самом начале:\n"
                "1. [EXCEL] — если пользователь просит таблицу, смету, расчеты. В конце добавь JSON блок.\n"
                "2. [PDF] — ЕСЛИ ПОЛЬЗОВАТЕЛЬ ПРОСИТ ДОКУМЕНТ, СОЧИНЕНИЕ, КП ИЛИ ОТЧЕТ. Весь текст после тега [PDF] пойдет в Word-документ.\n"
                "3. [TEXT] — для обычных ответов на вопросы.\n"
                "НИКОГДА не выводи исходный код Python."
            )
            
            messages = [{"role": "system", "content": system_prompt}] + [
                {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
            ]
            
            response = client.chat.completions.create(
                model=model_choice,
                messages=messages
            )
            full_reply = response.choices[0].message.content
            
            # Страховка на случай, если модель забыла тег, но пользователь просил документ
            if "[PDF]" not in full_reply and any(word in prompt.lower() for word in ["pdf", "файл", "сочинение", "предложение", "отчет", "документ", "смет"]):
                full_reply = "[PDF]\n" + full_reply

            skill_tag = "[TEXT]"
            reply_text = full_reply
            excel_data = None
            
            if "[EXCEL]" in full_reply:
                skill_tag = "[EXCEL]"
                parts = full_reply.split("```json")
                reply_text = parts[0].replace("[EXCEL]", "").strip()
                if len(parts) > 1:
                    try:
                        json_part = parts[1].split("```")
                        json_str = json_part[0].strip()
                        excel_data = json.loads(json_str)
                    except Exception:
                        excel_data = None
            elif "[PDF]" in full_reply:
                skill_tag = "[PDF]"
                reply_text = full_reply.replace("[PDF]", "").strip()
            elif "[TEXT]" in full_reply:
                skill_tag = "[TEXT]"
                reply_text = full_reply.replace("[TEXT]", "").strip()

            file_path = None
            if skill_tag == "[EXCEL]" and excel_data:
                status.update(label="Компилирую персональный Excel-файл...", state="running")
                file_path = "Коммерческий_отчет_Kobi.xlsx"
                df = pd.DataFrame(
                    excel_data.get("rows", []), 
                    columns=excel_data.get("columns", ["Параметр", "Значение"])
                )
                df.to_excel(file_path, index=False)
            elif skill_tag == "[PDF]":
                status.update(label="Генерация Word-документа...", state="running")
                file_path = "Kobi_Document.docx"
                word_buffer = generate_word_report("Документ от Kobi AI", reply_text)
                with open(file_path, "wb") as f:
                    f.write(word_buffer.getbuffer())

            status.update(label="Задача успешно выполнена!", state="complete", expanded=False)

        st.markdown(reply_text)
        
        if file_path and os.path.exists(file_path):
            file_name = os.path.basename(file_path)
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_name.endswith(".xlsx") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            with open(file_path, "rb") as f:
                st.download_button(
                    label=f"📥 Скачать готовый файл: {file_name}",
                    data=f,
                    file_name=file_name,
                    mime=mime_type,
                    key=f"new_{file_path}_{os.path.getmtime(file_path)}"
                )
            st.session_state.messages.append({"role": "assistant", "content": reply_text, "file_path": file_path})
        else:
            st.session_state.messages.append({"role": "assistant", "content": reply_text})
