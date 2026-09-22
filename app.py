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
    st.info("💡 Промышленный режим: Web Search (с защитой от пустых выдач) + Python Sandbox.")
    
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

st.title("🤖 Kobi — Автономный ИИ-Агент (Industrial Edition v2)")
st.caption(f"Текущий чат: **{st.session_state.current_chat}** | Статус: Защита от пустых поисковых выдач активна")

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
            "description": "Выполняет Python-код для создания файлов (Excel, Word, CSV) и расчетов.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Валидный Python код."
                    },
                    "description": "Описание задачи."
                },
                "required": ["code"]
            }
        }
    }
]

# --- ИСПОЛНИТЕЛИ С ГАРАНТИЕЙ РЕЗУЛЬТАТА ---
def search_web(query: str) -> str:
    results = []
    try:
        clean_q = query.replace("site:youtube.com", "").strip()
        with DDGS() as ddgs:
            for r in ddgs.text(clean_q, max_results=5):
                results.append({
                    "title": r.get("title"),
                    "href": r.get("href"),
                    "body": r.get("body")
                })
    except Exception:
        pass

    # ЖЕЛЕЗОБЕТОННЫЙ FALLBACK: если поиск пустой или упал, подставляем прямую ссылку на YouTube/Web
    if not results:
        formatted_q = query.replace(' ', '+')
        if any(w in query.lower() for w in ["ютуб", "youtube", "видео", "клип", "fc 27"]):
            results.append({
                "title": f"Смотреть видео по запросу: {query} на YouTube",
                "href": f"https://www.youtube.com/results?search_query={formatted_q}",
                "body": "Прямая ссылка на результаты поиска в YouTube."
            })
        else:
            results.append({
                "title": f"Результаты поиска: {query}",
                "href": f"https://html.duckduckgo.com/html/?q={formatted_q}",
                "body": "Прямая ссылка на поисковую выдачу."
            })

    return json.dumps(results, ensure_ascii=False)

def execute_python_code(code: str, description: str = "") -> str:
    output_buffer = io.StringIO()
    safe_globals = {"pd": pd, "json": json, "io": io, "Document": Document, "os": os}
    try:
        with contextlib.redirect_stdout(output_buffer):
            exec(code, safe_globals)
        
        captured_output = output_buffer.getvalue()
        created_files = [f for f in os.listdir('.') if f.endswith(('.xlsx', '.docx', '.csv', '.txt'))]

        return json.dumps({
            "status": "success", 
            "output": captured_output if captured_output else "Код выполнен успешно.",
            "files": created_files
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "error_message": str(e)}, ensure_ascii=False)

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
        with st.status("Kobi обрабатывает запрос...", expanded=True) as status:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=MASTER_API_KEY,
            )
            
            system_prompt = (
                "Ты — Kobi, элитный автономный ИИ-агент.\n"
                "ТВОИ ЖЕСТКИЕ ПРАВИЛА:\n"
                "1. Ты ВСЕГДА используешь инструмент search_web, когда тебя просят найти видео, ссылки, сайты или свежую информацию.\n"
                "2. Инструмент поиска гарантированно возвращает ссылки (включая прямые ссылки на YouTube). Ты ОБЯЗАН взять полученную ссылку и красиво вставить ее в ответ в формате Markdown: [Название](URL).\n"
                "3. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО говорить 'ничего не найдено', 'я не смог найти' или отказываться искать. Если инструмент вернул ссылку — ты сразу отдаешь ее пользователю.\n"
                "4. Никакого технического мусора и JSON. Только чистый коммерческий ответ с кликабельными ссылками."
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
                    status.update(label="Обрабатываю поисковую выдачу...", state="running")
                    
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

                    status.update(label="Формирую финальный ответ с ссылками...", state="running")
                    
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
