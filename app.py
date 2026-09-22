import os
import io
import json
import streamlit as st
import pandas as pd
from openai import OpenAI
from docx import Document

# Настройка страницы
st.set_page_config(
    page_title="Kobi — Agentic AI Platform", 
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
    st.markdown("### 🤖 Kobi Agent (Tools)")
    st.info("💡 Активен режим нативного Function Calling.")
    
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
    
    # DeepSeek на первом месте (по умолчанию), Claude в списке для ручного выбора
    model_choice = st.selectbox(
        "Модель", 
        [
            "deepseek/deepseek-chat",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-exp"
        ],
        index=0,
        format_func=lambda x: (
            "🚀 DeepSeek Chat (Основная / Бюджет)" if "deepseek" in x else
            "🧠 Claude 3.5 Sonnet (Премиум / Дорогая)" if "claude" in x else
            "⚡ Gemini Flash"
        )
    )

messages_list = st.session_state.chats[st.session_state.current_chat]

st.title("🤖 Kobi — Автономный Агент с Tool Use")
st.caption(f"Текущий чат: **{st.session_state.current_chat}** | Архитектура: OpenAI Function Calling")

# --- ОПРЕДЕЛЕНИЕ ИНСТРУМЕНТОВ (TOOLS) ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "create_excel_file",
            "description": "Создает и сохраняет Excel-файл (.xlsx) на основе переданных табличных данных в формате CSV.",
            "parameters": {
                "type": "object",
                "properties": {
                    "csv_content": {
                        "type": "string",
                        "description": "Табличные данные в формате CSV (с заголовками)."
                    },
                    "filename": {
                        "type": "string",
                        "description": "Имя файла, например 'buhgalteriya.xlsx'."
                    }
                },
                "required": ["csv_content", "filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_word_document",
            "description": "Создает и сохраняет Word-документ (.docx) с текстом отчета, договора или статьи.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Заголовок документа."
                    },
                    "content": {
                        "type": "string",
                        "description": "Текст или структура документа."
                    },
                    "filename": {
                        "type": "string",
                        "description": "Имя файла, например 'otchet.docx'."
                    }
                },
                "required": ["title", "content", "filename"]
            }
        }
    }
]

# --- ИСПОЛНИТЕЛИ ИНСТРУМЕНТОВ ---
def create_excel_file(csv_content: str, filename: str) -> str:
    try:
        df = pd.read_csv(io.StringIO(csv_content), sep=None, engine='python')
        if not filename.endswith('.xlsx'):
            filename += '.xlsx'
        df.to_excel(filename, index=False)
        return json.dumps({"status": "success", "file_path": filename, "message": f"Файл {filename} успешно создан."})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

def create_word_document(title: str, content: str, filename: str) -> str:
    try:
        doc = Document()
        doc.add_heading(title, level=1)
        for line in content.split('\n'):
            if line.strip():
                doc.add_paragraph(line.strip())
            else:
                doc.add_paragraph()
        if not filename.endswith('.docx'):
            filename += '.docx'
        doc.save(filename)
        return json.dumps({"status": "success", "file_path": filename, "message": f"Документ {filename} успешно создан."})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

available_functions = {
    "create_excel_file": create_excel_file,
    "create_word_document": create_word_document
}

# Вывод истории сообщений
for message in messages_list:
    with st.chat_message(message["role"]):
        if message.get("content"):
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
prompt = st.chat_input("Поставьте задачу для Kobi...")

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
        with st.status("Kobi анализирует задачу и выбирает инструменты...", expanded=True) as status:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=MASTER_API_KEY,
            )
            
            system_prompt = (
                "Ты — автономный коммерческий агент Kobi. У тебя есть инструменты для создания таблиц Excel и документов Word.\n"
                "Используй их активно, когда пользователь просит составить расчеты, сметы, таблицы, отчеты или документы.\n"
                "Действуй профессионально и автономно."
            )
            
            api_messages = [{"role": "system", "content": system_prompt}]
            for m in messages_list:
                if m["role"] in ["user", "assistant", "tool"]:
                    msg_dict = {"role": m["role"], "content": m.get("content")}
                    if "tool_calls" in m:
                        msg_dict["tool_calls"] = m["tool_calls"]
                    if "tool_call_id" in m:
                        msg_dict["tool_call_id"] = m["tool_call_id"]
                    if "name" in m:
                        msg_dict["name"] = m["name"]
                    api_messages.append(msg_dict)

            generated_file_path = None
            final_reply = ""

            try:
                response = client.chat.completions.create(
                    model=model_choice,
                    messages=api_messages,
                    tools=tools,
                    tool_choice="auto"
                )
                
                response_message = response.choices[0].message
                
                if response_message.tool_calls:
                    status.update(label="Выполняю инструменты (Function Calling)...", state="running")
                    
                    messages_list.append({
                        "role": "assistant",
                        "content": response_message.content,
                        "tool_calls": [tc.model_dump() for tc in response_message.tool_calls]
                    })
                    api_messages.append({
                        "role": "assistant",
                        "content": response_message.content,
                        "tool_calls": response_message.tool_calls
                    })

                    for tool_call in response_message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        if function_name in available_functions:
                            function_to_call = available_functions[function_name]
                            tool_output = function_to_call(**function_args)
                            
                            try:
                                res_json = json.loads(tool_output)
                                if res_json.get("status") == "success":
                                    generated_file_path = res_json.get("file_path")
                            except:
                                pass

                            messages_list.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": function_name,
                                "content": tool_output
                            })
                            api_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": function_name,
                                "content": tool_output
                            })

                    status.update(label="Формирую окончательный ответ...", state="running")
                    
                    second_response = client.chat.completions.create(
                        model=model_choice,
                        messages=api_messages
                    )
                    final_reply = second_response.choices[0].message.content
                else:
                    final_reply = response_message.content

            except Exception as e:
                st.error(f"⚠️ Ошибка агента `{model_choice}`: {e}")
                st.stop()

            status.update(label="Готово!", state="complete", expanded=False)

        st.markdown(final_reply)
        
        assistant_history_item = {"role": "assistant", "content": final_reply}
        
        if generated_file_path and os.path.exists(generated_file_path):
            assistant_history_item["file_path"] = generated_file_path
            file_name = os.path.basename(generated_file_path)
            mime_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" 
                if file_name.endswith(".xlsx") else 
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            with open(generated_file_path, "rb") as f:
                st.download_button(
                    label=f"📥 Скачать файл: {file_name}",
                    data=f,
                    file_name=file_name,
                    mime=mime_type,
                    key=f"new_{generated_file_path}_{os.path.getmtime(generated_file_path)}"
                )
        
        messages_list.append(assistant_history_item)
        st.rerun()
