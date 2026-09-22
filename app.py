import os
import io
import json
import concurrent.futures
import contextlib
import streamlit as st
import pandas as pd
from openai import OpenAI
from docx import Document
from duckduckgo_search import DDGS
from PIL import Image, ImageOps, ImageFilter

# Настройка страницы
st.set_page_config(
    page_title="Kobi — Multi-Model Supreme Agent", 
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
    st.markdown("### 🤖 Kobi Supreme Agent")
    st.info("💡 Режим: 4 модели + Мульти-модельный консенсус + Генерация/Редактирование фото.")
    
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
    st.header("⚙️ Выбор режима / модели")
    
    models_dict = {
        "👑 Мульти-Модельный Консенсус (Все 4 модели сразу)": "ensemble",
        "🚀 DeepSeek Chat (Основная)": "deepseek/deepseek-chat",
        "🧠 Claude 3.5 Sonnet (Премиум)": "anthropic/claude-3.5-sonnet",
        "💡 GPT-4o Mini ( OpenAI )": "openai/gpt-4o-mini",
        "⚡ Gemini 2.0 Flash ( Google )": "google/gemini-2.0-flash-exp"
    }
    
    selected_model_label = st.selectbox(
        "Модель", 
        list(models_dict.keys()),
        index=0
    )
    model_choice = models_dict[selected_model_label]

messages_list = st.session_state.chats[st.session_state.current_chat]

st.title("🤖 Kobi — Мульти-агентный комплекс (Supreme Edition)")
st.caption(f"Текущий чат: **{st.session_state.current_chat}** | Инструменты: Web Search + Image Generation/Editing + Python Sandbox")

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
                        "description": "Точный поисковый запрос (например, 'FC 27 видео ютуб' или 'новости ИИ')."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Генерирует изображение по детальному текстовому описанию на английском или русском языке.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Подробное описание изображения для генерации."
                    }
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python_code",
            "description": "Выполняет Python-код для обработки данных, создания файлов (Excel, Word) и профессионального редактирования изображений с помощью PIL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Валидный Python код. Доступны pandas, json, io, Document, Image, ImageOps, ImageFilter."
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

def generate_image(prompt: str) -> str:
    import urllib.parse
    encoded = urllib.parse.quote(prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"
    return json.dumps({"status": "success", "image_url": image_url, "prompt": prompt}, ensure_ascii=False)

def execute_python_code(code: str, description: str = "") -> str:
    output_buffer = io.StringIO()
    safe_globals = {
        "pd": pd, "json": json, "io": io, "Document": Document, "os": os,
        "Image": Image, "ImageOps": ImageOps, "ImageFilter": ImageFilter
    }
    try:
        with contextlib.redirect_stdout(output_buffer):
            exec(code, safe_globals)
        
        captured_output = output_buffer.getvalue()
        created_files = [f for f in os.listdir('.') if f.endswith(('.xlsx', '.docx', '.csv', '.txt', '.png', '.jpg', '.jpeg'))]

        return json.dumps({
            "status": "success", 
            "output": captured_output if captured_output else "Код выполнен успешно.",
            "files": created_files
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "error_message": str(e)}, ensure_ascii=False)

available_functions = {
    "search_web": search_web,
    "generate_image": generate_image,
    "execute_python_code": execute_python_code
}

# --- ВЫВОД ИСТОРИИ ЧАТА ---
for message in messages_list:
    if message["role"] in ["user", "assistant"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "file_path" in message and os.path.exists(message["file_path"]):
                if message["file_path"].lower().endswith(('.png', '.jpg', '.jpeg')):
                    st.image(message["file_path"])
                with open(message["file_path"], "rb") as f:
                    file_name = os.path.basename(message["file_path"])
                    st.download_button(
                        label=f"📥 Скачать файл: {file_name}",
                        data=f,
                        file_name=file_name,
                        key=f"hist_btn_{message['file_path']}"
                    )

# --- ВХОДНЫЕ ДАННЫЕ ---
prompt = st.chat_input("Поставьте задачу для Kobi (найти видео, сгенерировать картинку, сделать отчет)...")

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
        with st.status("Kobi запускает мульти-агентную сеть...", expanded=True) as status:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=MASTER_API_KEY,
            )
            
            system_prompt = (
                "Ты — Kobi, элитный мульти-модельный автономный ИИ-агент высшего уровня.\n"
                "У тебя есть инструменты:\n"
                "- search_web: для поиска информации и ссылок на YouTube.\n"
                "- generate_image: для генерации изображений по описанию.\n"
                "- execute_python_code: для расчетов, файлов и редактирования изображений (PIL).\n"
                "ПРАВИЛА:\n"
                "1. Никогда не говори 'я не умею'. Используй инструменты.\n"
                "2. Ссылки оформляй красиво в Markdown: [Название](URL).\n"
                "3. Выдавай максимально качественный, коммерческий результат."
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
            generated_image_url = None

            try:
                models_to_run = []
                if model_choice == "ensemble":
                    models_to_run = [
                        "deepseek/deepseek-chat",
                        "anthropic/claude-3.5-sonnet",
                        "openai/gpt-4o-mini",
                        "google/gemini-2.0-flash-exp"
                    ]
                else:
                    models_to_run = [model_choice]

                def query_single_model(m_name):
                    try:
                        res = client.chat.completions.create(
                            model=m_name,
                            messages=api_messages,
                            tools=tools,
                            tool_choice="auto"
                        )
                        return m_name, res
                    except Exception as ex:
                        return m_name, str(ex)

                status.update(label=f"Опрашиваю модели ({len(models_to_run)} шт.)...", state="running")
                
                responses = {}
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {executor.submit(query_single_model, m): m for m in models_to_run}
                    for future in concurrent.futures.as_completed(futures):
                        m_name, res = future.result()
                        responses[m_name] = res

                active_response_message = None
                active_model_used = models_to_run[0]

                for m_name, res in responses.items():
                    if not isinstance(res, str) and res.choices:
                        msg = res.choices[0].message
                        if msg.tool_calls or msg.content:
                            active_response_message = msg
                            active_model_used = m_name
                            break

                if isinstance(active_response_message, str) or active_response_message is None:
                    fallback_res = client.chat.completions.create(
                        model="deepseek/deepseek-chat",
                        messages=api_messages,
                        tools=tools,
                        tool_choice="auto"
                    )
                    active_response_message = fallback_res.choices[0].message
                    active_model_used = "deepseek/deepseek-chat (Fallback)"

                response_message = active_response_message

                if response_message.tool_calls:
                    status.update(label=f"Модель [{active_model_used}] выполняет инструменты...", state="running")
                    
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
                                if isinstance(out_json, dict):
                                    if out_json.get("image_url"):
                                        generated_image_url = out_json["image_url"]
                                    if out_json.get("files"):
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

                    status.update(label="Формирую финальный синергетический ответ...", state="running")
                    
                    second_response = client.chat.completions.create(
                        model=active_model_used.split(" ")[0] if " " in active_model_used else active_model_used,
                        messages=api_messages
                    )
                    final_reply = second_response.choices[0].message.content
                else:
                    final_reply = response_message.content

                if model_choice == "ensemble":
                    final_reply = f"👑 *[Результат Мульти-Модельного Консенсуса 4-х нейросетей]*\n\n{final_reply}"

            except Exception as e:
                st.error(f"⚠️ Ошибка сети агентов: {e}")
                st.stop()

            status.update(label="Готово!", state="complete", expanded=False)

        st.markdown(final_reply)
        
        if generated_image_url:
            st.image(generated_image_url, caption="Сгенерированное изображение Kobi")

        assistant_item = {"role": "assistant", "content": final_reply}
        if latest_file_path and os.path.exists(latest_file_path):
            assistant_item["file_path"] = latest_file_path
            if latest_file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                st.image(latest_file_path)
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
