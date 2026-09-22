import os
import io
import re
import base64
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
            "google/gemini-flash-1.5",
            "deepseek/deepseek-chat",
            "anthropic/claude-3-haiku",
            "anthropic/claude-3.5-sonnet"
        ],
        format_func=lambda x: (
            "⚡ Gemini Flash 1.5 (Лучшая для голоса)" if "gemini" in x else 
            ("🚀 DeepSeek Chat" if "deepseek" in x else
             ("🍃 Claude 3 Haiku" if "haiku" in x else "👑 Claude 3.5 Sonnet (Премиум)"))
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

# --- ГОЛОСОВОЙ И ТЕКСТОВЫЙ ВВОД ---
audio_value = st.audio_input("🎙️ Записать голосовое сообщение")
text_prompt = st.chat_input("Спросите что угодно или отправьте задачу...")

prompt = None

if audio_value:
    audio_bytes = audio_value.read()
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    
    with st.spinner("🎙️ Kobi слушает и расшифровывает голос..."):
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=MASTER_API_KEY,
        )
        try:
            transcribe_res = client.chat.completions.create(
                model="google/gemini-flash-1.5",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": "Напиши дословно текст того, что пользователь сказал в этом голосовом сообщении. Выведи только распознанный текст без лишних комментариев."
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:audio/wav;base64,{audio_base64}"}
                            }
                        ]
                    }
                ]
            )
            prompt = transcribe_res.choices[0].message.content.strip()
            prompt = f"🎙️ [Голос] {prompt}"
        except Exception as e:
            st.error(f"Не удалось распознать голосовое сообщение: {e}")

if text_prompt:
    prompt = text_prompt

# Обработка запроса
if prompt:
    if not MASTER_API_KEY:
        st.error("Укажите валидный OpenRouter API-ключ в настройках Streamlit Secrets.")
        st.stop()

    messages_list.append({"role": "user", "content": prompt})
    
    if st.session_state.current_chat.startswith("💬 Новый чат") or st.session_state.current_chat.startswith("Диалог #"):
        clean_title = prompt.replace("🎙️ [Голос]", "").strip()
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
                "1. Если просят таблицу, смету, расчеты — начни ответ с тега [EXCEL] и выведи данные в виде CSV-таблицы внутри блока ```csv ... ```.\n"
                "2. Если просят документ, презентацию, отчет, структуру — начни с тега [PDF].\n"
                "3. Для остальных ответов используй [TEXT].\n"
                "НИКОГДА не выводи исходный код Python."
            )
            
            api_messages = [{"role": "system", "content": system_prompt}] + [
                {"role": m["role"], "content": m["content"]} for m in messages_list
            ]
            
            try:
                response = client.chat.completions.create(
                    model=model_choice,
                    messages=api_messages
                )
                full_reply = response.choices[0].message.content
            except Exception as e:
                st.error(f"⚠️ Ошибка от провайдера модели `{model_choice}`: {e}")
                st.stop()
            
            clean_prompt_check = prompt.replace("🎙️ [Голос]", "").lower()
            if "[PDF]" not in full_reply and "[EXCEL]" not in full_reply and any(w in clean_prompt_check for w in ["файл", "презентац", "структур", "отчет", "документ", "смет", "таблиц"]):
                full_reply = "[PDF]\n" + full_reply

            skill_tag = "[TEXT]"
            reply_text = full_reply
            csv_data = None
            
            if "[EXCEL]" in full_reply:
                skill_tag = "[EXCEL]"
                parts = full_reply.split("```csv")
                reply_text = parts[0].replace("[EXCEL]", "").strip()
                if len(parts) > 1:
                    sub_parts = parts[1].split("```")
                    csv_data = sub_parts[0].strip()
            elif "[PDF]" in full_reply:
                skill_tag = "[PDF]"
                reply_text = full_reply.replace("[PDF]", "").strip()
            elif "[TEXT]" in full_reply:
                skill_tag = "[TEXT]"
                reply_text = full_reply.replace("[TEXT]", "").strip()

            file_path = None
            if skill_tag == "[EXCEL]" and csv_data:
                status.update(label="Компилирую Excel-файл...", state="running")
                file_path = "Коммерческий_отчет_Kobi.xlsx"
                try:
                    df = pd.read_csv(io.StringIO(csv_data), sep=None, engine='python')
                    df.to_excel(file_path, index=False)
                except Exception:
                    df = pd.DataFrame([["Ошибка", "Не удалось распарсить CSV"]])
                    df.to_excel(file_path, index=False)
            elif skill_tag == "[PDF]":
                status.update(label="Генерация Word-документа...", state="running")
                file_path = "Kobi_Document.docx"
                word_buffer = generate_word_report("Документ от Kobi AI", reply_text)
                with open(file_path, "wb") as f:
                    f.write(word_buffer.getbuffer())

            status.update(label="Готово!", state="complete", expanded=False)

        st.markdown(reply_text)
        
        if file_path and os.path.exists(file_path):
            file_name = os.path.basename(file_path)
            mime_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" 
                if file_name.endswith(".xlsx") else 
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            with open(file_path, "rb") as f:
                st.download_button(
                    label=f"📥 Скачать файл: {file_name}",
                    data=f,
                    file_name=file_name,
                    mime=mime_type,
                    key=f"new_{file_path}_{os.path.getmtime(file_path)}"
                )
            messages_list.append({"role": "assistant", "content": reply_text, "file_path": file_path})
        else:
            messages_list.append({"role": "assistant", "content": reply_text})
        
        st.rerun()
