import os
import json
import streamlit as st
import pandas as pd
from openai import OpenAI

# Настройка страницы
st.set_page_config(page_title="Kobi — Коммерческий AI Агент", page_icon="🤖", layout="wide")

st.markdown("""
    
""", unsafe_allow_html=True)

st.title("🤖 Kobi — Автономный Коммерческий Агент")
st.caption("Профессиональный мультимодельный ассистент для бизнеса.")

# ЖЕСТКО ЗАШИТЫЙ КЛЮЧ (для клиента поле ввода скрыто, ничего вводить не нужно)
# Можешь вставить сюда свой ключ в кавычках, чтобы он работал постоянно навсегда:
MASTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
with st.sidebar:
    st.header("⚙️ Панель управления")
    model_choice = st.selectbox(
        "Выбор модели", 
        ["deepseek/deepseek-chat", "anthropic/claude-3.5-sonnet", "openai/gpt-4o-mini"]
    )
    st.markdown("---")
    st.success("✅ Система подключена и готова к работе.")

# Инициализация истории чата
if "messages" not in st.session_state:
    st.session_state.messages = []

# Вывод истории
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "file_path" in message and os.path.exists(message["file_path"]):
            with open(message["file_path"], "rb") as f:
                file_name = os.path.basename(message['file_path'])
                st.download_button(
                    label=f"📥 Скачать файл: {file_name}",
                    data=f,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"hist_{message['file_path']}_{os.path.getmtime(message['file_path'])}"
                )

# Обработка ввода
if prompt := st.chat_input("Какую задачу нужно решить? (например: 'Сделай смету расходов на офис')"):
    if not MASTER_API_KEY or MASTER_API_KEY.startswith("sk-or-v1-..."):
        st.error("Пожалуйста, укажи свой реальный OpenRouter API-ключ в переменной MASTER_API_KEY внутри кода app.py.")
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
                "Если пользователь просит таблицу, отчет, смету или расчеты:\n"
                "1. Напиши навык в начале: [EXCEL]\n"
                "2. Дай деловой ответ пользователю.\n"
                "3. В самом конце ответа добавь блок данных в формате JSON строго по шаблону:\n"
                "```json\n"
                "{\n"
                '  "columns": ["Колонка 1", "Колонка 2", "Колонка 3"],\n'
                '  "rows": [\n'
                '    ["Значение 1", "Значение 2", "Значение 3"],\n'
                '    ["Значение 4", "Значение 5", "Значение 6"]\n'
                "  ]\n"
                "}\n"
                "```\n"
                "Если файлы не нужны, пиши навык [TEXT] и просто отвечай на вопрос без JSON блока.\n"
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
                        json_str = parts[1].split("```")[0].strip()
                        excel_data = json.loads(json_str)
                    except Exception:
                        excel_data = None
            elif "[TEXT]" in full_reply:
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

            status.update(label="Задача успешно выполнена!", state="complete", expanded=False)

        st.markdown(reply_text)
        
        if file_path and os.path.exists(file_path):
            file_name = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                st.download_button(
                    label=f"📥 Скачать готовый отчёт: {file_name}",
                    data=f,
                    file_name=file_name,
                    key=f"new_{file_path}_{os.path.getmtime(file_path)}"
                )
            st.session_state.messages.append({"role": "assistant", "content": reply_text, "file_path": file_path})
        else:
            st.session_state.messages.append({"role": "assistant", "content": reply_text})