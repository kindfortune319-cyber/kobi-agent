import os
import json
import io
import re
import base64
import requests
import streamlit as st
import pandas as pd
from openai import OpenAI
from docx import Document

# Настройка страницы
st.set_page_config(page_title="Kobi — AI Platform", page_icon="🤖", layout="wide")

MASTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ (АККАУНТЫ И ЧАТЫ) ---
if "user" not in st.session_state:
    st.session_state.user = None  # None = гость (не вошел)

if "chats" not in st.session_state:
    st.session_state.chats = {"💬 Новый чат": []}
if "current_chat" not in st.session_state:
    st.session_state.current_chat = "💬 Новый чат"

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.markdown("### 🤖 Kobi Intelligence")
    
    # Блок авторизации и аккаунта
    if st.session_state.user is None:
        st.info("👋 Вы вошли как **Гость**. Доступны базовые модели.")
        with st.expander("🔑 Вход / Регистрация"):
            username_input = st.text_input("Имя пользователя / Email")
            if st.button("Продолжить", use_container_width=True):
                if username_input:
                    st.session_state.user = {"username": username_input, "pro": False}
                    st.success(f"Добро пожаловать, {username_input}!")
                    st.rerun()
    else:
        user_info = st.session_state.user
        st.markdown(f"👤 **{user_info['username']}**")
        if user_info["pro"]:
            st.success("👑 Статус: **PRO Подписка активна**")
        else:
            st.warning("⚡ Статус: **Free (Базовый)**")
            if st.button("💎 Оформить PRO (Claude)", use_container_width=True):
                st.session_state.user["pro"] = True
                st.balloons()
                st.rerun()
        
        if st.button("🚪 Выйти из аккаунта", use_container_width=True):
            st.session_state.user = None
            st.rerun()

    st.markdown("---")
    
    # Кнопка нового чата
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
    
    # Стабильные идентификаторы моделей на OpenRouter
    model_choice = st.selectbox(
        "Модель", 
        [
            "deepseek/deepseek-chat",            # Free
            "google/gemini-flash-1.5",           # Free (стабильная Gemini)
            "anthropic/claude-3-haiku",          # Free / PRO
            "anthropic/claude-3.5-sonnet"        # 🔒 PRO (премиум для презентаций и структуры)
        ],
        format_func=lambda x: f"🚀 DeepSeek Chat (Free)" if "deepseek" in x else 
                             (f"⚡ Gemini Flash 1.5 (Free)" if "gemini" in x else
                              (f"🍃 Claude 3 Haiku" if "haiku" in x else f"👑 Claude 3.5 Sonnet (PRO)"))
    )

messages_list = st.session_state.chats[st.session_state.current_chat]

st.title("🤖 Kobi — Автономный Коммерческий Агент")
st.caption(f"Текущий чат: **{st.session_state.current_chat}**")

is_pro_model = "sonnet" in model_choice
user_is_pro = st.session_state.user and st.session_state.user.get("pro", False)

if is_pro_model and not user_is_pro:
    st.warning("🔒 **Claude 3.5 Sonnet доступна только по PRO-подписке.** Оформите подписку в боковой панели или выберите бесплатную модель.")

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

# Вывод истории сообщений текущего чата
for message in messages_list:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "file_path" in message and os.path.exists(message["file_path"]):
            with open(message["file_path"], "rb") as f:
                file_name = os.path.basename(message['file_path'])
                mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_name.endswith(".xlsx") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                st.download_button(
                    label=f"📥 Скачать файл: {file_name}",
                    data=f,
                    file_name=file_name,
                    mime=mime_type,
                    key=f"hist_{message['file_path']}_{os.path.getmtime(message['file_path'])}"
                )

# --- ГОЛОСОВОЙ ВВОД (МИКРОФОН) ---
audio_value = st.audio_input("🎙️ Записать голосовое сообщение")

prompt = None
if audio_value:
    with st.spinner("Распознаю голос через Whisper..."):
        try:
            audio_bytes = audio_value.read()
            b64_audio = base64.b64encode(audio_bytes).decode('utf-8')
            headers = {"Authorization": f"Bearer {MASTER_API_KEY}"}
            payload = {"model": "openai/whisper-1", "file": b64_audio}
            res = requests.post("https://openrouter.ai/api/v1/audio/transcriptions", headers=headers, json=payload)
            if res.status_code == 200:
                prompt = res.json().get("text", "")
            else:
                st.error("Не удалось расшифровать аудио.")
        except Exception as e:
            st.error(f"Ошибка голосового ввода: {e}")

text_prompt = st.chat_input("Спросите что угодно или отправьте задачу...")
if text_prompt:
    prompt = text_prompt

# Обработка сообщения
if prompt:
    if is_pro_model and not user_is_pro:
        st.error("Для отправки запроса этой модели необходима PRO-подписка.")
        st.stop()
        
    if not MASTER_API_KEY or MASTER_API_KEY.startswith("sk-or-v1-..."):
        st.error("Укажите валидный OpenRouter API-ключ.")
        st.stop()

    messages_list.append({"role": "user", "content": prompt})
    
    if st.session_state.current_chat.startswith("💬 Новый чат") or st.session_state.current_chat.startswith("Диалог #"):
        new_name = (prompt[:22] + '...') if len(prompt) > 22 else prompt
        st.session_state.chats[new_name] = messages_list
        del st.session_state.chats[st.session_state.current_chat]
        st.session_state.current_chat = new_name

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Kobi обрабатывает запрос...", expanded=True) as status:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=MASTER_API_KEY,
            )
            
            system_prompt = (
                "Ты — автономный коммерческий агент Kobi. Твоя задача — решать бизнес-задачи.\n"
                "СТРОГОЕ ПРАВИЛО: Каждый ответ ты ОБЯЗАН начинать с одного из тегов в самом начале:\n"
                "1. [EXCEL] — если просят таблицу, смету, расчеты. В конце добавь JSON блок.\n"
                "2. [PDF] — если просят документ, презентацию, структуру, сочинение, КП или отчет. Текст пойдет в Word.\n"
                "3. [TEXT] — для обычных ответов.\n"
                "НИКОГДА не выводи исходный код Python."
            )
            
            api_messages = [{"role": "system", "content": system_prompt}] + [
                {"role": m["role"], "content": m["content"]} for m in messages_list
            ]
            
            # ЗАЩИЩЕННЫЙ ВЫЗОВ API (не падает с красным экраном)
            try:
                response = client.chat.completions.create(
                    model=model_choice,
                    messages=api_messages
                )
                full_reply = response.choices[0].message.content
            except Exception as e:
                st.error(f"⚠️ Ошибка от провайдера модели `{model_choice}`: {e}. Пожалуйста, выберите другую модель в боковой панели.")
                st.stop()
            
            if "[PDF]" not in full_reply and any(w in prompt.lower() for w in ["pdf", "файл", "презентац", "структур", "сочинение", "предложение", "отчет", "документ", "смет"]):
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
                status.update(label="Компилирую Excel-файл...", state="running")
                file_path = "Коммерческий_отчет_Kobi.xlsx"
                df = pd.DataFrame(excel_data.get("rows", []), columns=excel_data.get("columns", ["Параметр", "Значение"]))
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
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_name.endswith(".xlsx") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
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
