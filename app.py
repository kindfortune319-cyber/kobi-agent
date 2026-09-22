import os
import io
import json
import contextlib
import streamlit as st
import pandas as pd
from openai import OpenAI
from docx import Document
from duckduckgo_search import DDGS

# Настройка страницы
st.set_page_config(
    page_title="Kobi — Autonomous Industrial Agent", 
    page_icon="🤖", 
    layout="wide"
)

MASTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")

# --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ ЧАТОВ ---
if "chats" not in st.session_state:
    st.session_state.chats = {"💬 Новый чат": []}
if "current_chat" not in st.session_state:
    st.session_state.current_chat = "💬 Новый чат"

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.markdown("### 🤖 Kobi Industrial Agent")
    st.info("💡 Активен промышленный режим: Web Search + Python Sandbox + Auto-File Generation.")
    
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
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-exp"
        ],
        index=0,
        format_func=lambda x: (
            "🚀 DeepSeek Chat (Основная / Быстрая)" if "deepseek" in x else
            "🧠 Claude 3.5 Sonnet (Премиум)" if "claude" in x else
            "⚡ Gemini Flash"
        )
    )

messages_list = st.session_state.chats[st.session_state.current_chat]

st.title("🤖 Kobi — Автономный ИИ-Агент (Industrial Edition)")
st.caption(f"Текущий чат: **{st.session_state.current_chat}** | Архитектура: Multi-Tool Agent Loop")

# --- ИНСТРУМЕНТЫ АГЕНТА ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Ищет информацию, статьи, сайты и ссылки на видео (включая YouTube) в интернете.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Точный поисковый запрос (например, 'FC 27 видео ютуб' или 'последние новости')."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python_code",
            "description": (
                "Универсальный инструмент выполнения Python-кода. Используй для создания файлов (Excel .xlsx, Word .docx, CSV), "
                "сложных расчетов, обработки данных и решения технических задач."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Валидный Python код. Доступны pandas, json, io, Document."
                    },
                    "description": "Описание задачи."
                },
                "required": ["code"]
            }
        }
    }
]

# --- ИСПОЛНИТЕЛИ ---
def search_web(query: str) -> str:
    try:
        results = []
        # Улучшенный поисковый запрос для YouTube если требуется
        search_query = query
        if any(w in query.lower() for w in ["ютуб", "youtube", "видео", "клип"]):
            if "site:youtube.com" not in search_query:
                search_query += " site:youtube.com"

        with DDGS() as ddgs:
            for r in ddgs.text(search_query, max_results=5):
                results.append({
                    "title": r.get("title"),
                    "href": r.get("href"),
                    "body": r.get("body")
                })
        
        # Если с точным фильтром ничего не нашлось, ищем без него
        if not results:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=5):
                    results.append({
                        "title": r.get("title"),
                        "href": r.get("href"),
                        "body": r.get("body")
                    })

        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps([{"error": str(e)}], ensure_ascii=False)

def execute_python_code(code: str, description: str = "") -> str:
    output_buffer = io.StringIO()
    safe_globals = {
        "pd": pd,
        "json": json,
        "io": io,
        "Document": Document,
        "os": os,
    }
    try:
        with contextlib.redirect_stdout(output_buffer):
            exec(code, safe_globals)
        
        captured_output = output_buffer.getvalue()
        
        # Ищем созданные файлы в директории
        created_files = []
        for f_name in os.listdir('.'):
            if f_name.endswith(('.xlsx', '.docx', '.csv', '.txt')) and os.path.getmtime(f_name) > (os.time() - 15 if hasattr(os, 'time') else 0):
                created_files.append(f_name)

        return json.dumps({
            "status": "success", 
            "output": captured_output if captured_output else "Код выполнен успешно.",
            "files": created_files
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "status": "error", 
            "error_message": str(e)
        }, ensure_ascii=False)

available_functions = {
    "search_web": search_web,
    "execute_python_code": execute_python_code
}

# --- ВЫВОД ИСТОРИИ ЧАТА ---
for message in messages_list:
    if message["role"] in ["user", "assistant"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "file_path" in message and os.path.exists(message["file_path"]):
                with open(message["file_path"], "rb") as f:
                    file_name = os.path.basename(message["file_path"])
                    st.download_button(
                        label=f"📥 Скачать файл: {file_name}",
                        data=f,
                        file_name=file_name,
                        key=f"hist_btn_{message['file_path']}"
                    )

# --- ВХОДНЫЕ ДАННЫЕ ---
prompt = st.chat_input("Поставьте задачу для Kobi (например: найди видео про... или сделай отчет)...")

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
        with st.status("Kobi выполняет задачу в фоновом режиме...", expanded=True) as status:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=MASTER_API_KEY,
            )
            
            system_prompt = (
                "Ты — Kobi, элитный автономный ИИ-агент коммерческого уровня.\n"
                "У тебя есть инструменты: search_web (поиск в сети и на YouTube) и execute_python_code (создание файлов, расчеты, код).\n"
                "ПРАВИЛА:\n"
                "1. Никогда не говори 'я не умею' или 'у меня нет инструментов'. Ты умеешь всё через свои инструменты.\n"
                "2. Если пользователь просит найти видео, ссылки, статьи или свежие данные — СРАЗУ вызывай search_web.\n"
                "3. Получив результаты поиска, выбери лучшие ссылки и оформь их в виде кликабельных Markdown-ссылок: [Название](URL).\n"
                "4. Если нужно создать документ, таблицу или решить вычислительную задачу — пиши Python-код через execute_python_code.\n"
                "5. Никакого технического мусора, JSON-строк или скобок пользователю показывать нельзя. Только чистый, профессиональный ответ."
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

            final_reply = ""
            latest_file_path = None

            try:
                response = client.chat.completions.create(
                    model=model_choice,
                    messages=api_messages,
                    tools=tools,
                    tool_choice="auto"
                )
                
                response_message = response.choices[0].message
                
                if response_message.tool_calls:
                    status.update(label="Агент применяет инструменты...", state="running")
                    
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
                            
                            # Проверяем файлы если это python sandbox
                            try:
                                out_json = json.loads(tool_output)
                                if isinstance(out_json, dict) and out_json.get("files"):
                                    latest_file_path = out_json["files"][-1]
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

                    status.update(label="Формирую экспертный результат...", state="running")
                    
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
        
        assistant_item = {"role": "assistant", "content": final_reply}
        if latest_file_path and os.path.exists(latest_file_path):
            assistant_item["file_path"] = latest_file_path
            with open(latest_file_path, "rb") as f:
                file_name = os.path.basename(latest_file_path)
                st.download_button(
                    label=f"📥 Скачать файл: {file_name}",
                    data=f,
                    file_name=file_name,
                    key=f"new_btn_{latest_file_path}"
                )

        messages_list.append(assistant_item)
        st.rerun()
