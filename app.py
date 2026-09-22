import os
import io
import re
import streamlit as st
import pandas as pd
from openai import OpenAI
from docx import Document

# Настройка страницы
st.set_page_config(
    page_title="Kobi — AI Platform", 
    page_icon="🤖", 
    layout="wide"
)

MASTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ ЧАТОВ ---
if "chats" not in st.session_state:
    st.session_state.chats = {"💬 Новый чат": []}
if "current_chat" not in st.session_state:
    st.session_state.current_chat = "💬 Новый чат"

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.markdown("### 🤖 Kobi Intelligence")
    st.info("💡 Добро пожаловать! Все модели и функции полностью разблокированы.")
    
    if st.button("➕ Новый чат", use_container_width=True):
        new_name = f"Диалог #{len(st.session_state.chats) + 1}"
        st.session_state.chats[new_name] = []
        st.session_state.current_chat = new_name
        st.rerun()

    st.markdown("#### 📜 История чатов")
    chat_names = list(st.session_state.chats.keys())
    selected_chat = st.selectbox(
        "Выберите чат", 
        chat_names, 
        index=chat_names.index(st.session_state.current_chat),
        label_visibility="collapsed"
    )
    if selected_chat != st.session_state.current_chat:
        st.session_state.current_chat = selected_chat
        st.rerun()

    st.markdown("---")
    st.header("⚙️ Выбор модели")
    
    model_choice = st.selectbox(
        "Модель", 
        [
            "deepseek/deepseek-chat",
            "anthropic/claude-3-haiku",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.5-flash"
        ],
        format_func=lambda x: (
            "🚀 DeepSeek Chat" if "deepseek" in x else
            ("🍃 Claude 3 Haiku" if "haiku" in x else
             ("👑 Claude 3.5 Sonnet (Премиум)" if "sonnet" in x else "⚡ Gemini Flash"))
        )
    )

messages_list = st.session_state.chats[st.session_state.current_chat]

st.title("🤖 Kobi — Автономный Коммерческий Агент")
st.caption(f"Текущий чат: **{st.session_state.current_chat}**")

def generate_word_report(title, content):
    doc = Document()
    doc.add_heading(title, level=1)
    clean_content = re.sub(r'[*#_`]', '', content)
    for line in clean_content.split('\n'):
        if line.strip():
            doc.add_paragraph(line.strip())
        else:
            doc.add_paragraph()
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# Вывод истории сообщений
for message in messages_list:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "file_path" in message and os.path.exists(message["file_path"]):
            with open(message["file_path"], "rb") as f:
                file_name = os.path.basename(message['file_path'])
                mime_type = (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" 
                    if file_name.endswith(".xlsx") else 
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                st.download_button(
                    label=f"📥 Скачать файл: {file_name}",
                    data=f,
                    file_name=file_name,
                    mime=mime_type,
                    key=f"hist_{message['file_path']}_{os.path.getmtime(message['file_path'])}"
                )

# --- ТЕКСТОВЫЙ ВВОД ---
prompt = st.chat_input("Спросите что угодно или отправьте задачу...")

# Обработка запроса
if prompt:
    if not MASTER_API_KEY:
        st.error("Укажите валидный OpenRouter API-ключ в настройках Streamlit Secrets.")
        st.stop()

    messages_list.append({"role": "user", "content": prompt})
    
    if st.session_state.current_chat.startswith("💬 Новый чат") or st.session_state.current_chat.startswith("Диалог #"):
        clean_title = prompt.strip()
        new_name = (clean_title[:22] + '...') if len(clean_title) > 22 else clean_title
        st.session_state.chats[new_name] = messages_list
        del st.session_state.chats[st.session_state.current_chat]
        st.session_state.current_chat = new_name

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Kobi обрабатывает задачу...", expanded=True) as status:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=MASTER_API_KEY,
            )
            
            system_prompt = (
                "Ты — автономный коммерческий агент Kobi. Твоя задача — решать бизнес-задачи.\n"
                "СТРОГОЕ ПРАВИЛО:\n"
                "1. Если просят таблицу, смету, расчеты — начни ответ с тега [EXCEL] и выведи данные в виде CSV-таблицы внутри блока ```csv ...
