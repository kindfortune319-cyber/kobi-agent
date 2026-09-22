import os
import io
import json
import base64
import requests
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
    page_title="Kobi — Supreme Multi-Model Consensus", 
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
    st.info("💡 Режим: Мульти-Модельный Консенсус + Flux.1 Native API + Python Sandbox.")
    
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
        "👑 Мульти-Модельный Консенсус (Синтез 4-х ИИ)": "ensemble",
        "🚀 DeepSeek Chat (Основная)": "deepseek/deepseek-chat",
        "🧠 Claude 3.5 Sonnet (Премиум)": "anthropic/claude-3.5-sonnet",
        "💡 GPT-4o Mini (OpenAI)": "openai/gpt-4o-mini",
        "⚡ Gemini 2.0 Flash (Google)": "google/gemini-2.0-flash-exp"
    }
    
    selected_model_label = st.selectbox(
        "Модель", 
        list(models_dict.keys()),
        index=0
    )
    model_choice = models_dict[selected_model_label]

messages_list = st.session_state.chats[st.session_state.current_chat]

st.title("🤖 Kobi — Мульти-агентный комплекс (Supreme Consensus)")
st.caption(f"Текущий чат: **{st.session_state.current_chat}** | Движок фото: **OpenRouter FLUX.1 Schnell**")

# --- ИНСТРУМЕНТЫ АГЕНТА (Исправлены схемы под строгий стандарт OpenAI) ---
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
                        "description": "Точный поисковый запрос."
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
            "description": "Генерирует фотореалистичное изображение через официальный движок Flux.1 на OpenRouter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Детальное описание генерации на английском языке."
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
            "description": "Выполняет Python-код для обработки данных, файлов (Excel, Word) и редактирования фото.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Валидный Python код."
                    },
                    "description": {
                        "type": "string",
                        "description": "Описание задачи."
                    }
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
        if any(w in query.lower() for w in ["ютуб", "youtube", "видео", "клип"]):
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
    enhanced_prompt = f"{prompt}, highly detailed, 8k resolution, photorealistic, professional sports photography, perfect anatomy, masterpiece"
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/images",
            headers={
                "Authorization": f"Bearer {MASTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://kobi-agent.streamlit.app",
                "X-Title": "Kobi Supreme Agent"
            },
            json={
                "model": "black-forest-labs/flux-1-schnell",
                "prompt": enhanced_prompt,
                "aspect_ratio": "16:9"
            }
        )
        if response.status_code == 200:
            res_data = response.json()
            if "data" in res_data and len(res_data["data"]) > 0:
                item = res_data["data"][0]
                if "b64_json" in item:
                    img_bytes = base64.b64decode(item["b64_json"])
                    file_name = f"flux_gen_{os.urandom(4).hex()}.png"
                    with open(file_name, "wb") as f:
                        f.write(img_bytes)
                    return json.dumps({"status": "success", "file_path": file_name, "prompt": prompt}, ensure_ascii=False)
        
        return json.dumps({"status": "error", "error_message": f"OpenRouter Image API Error: {response.text}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "error_message": str(e)}, ensure_ascii=False)

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
prompt = st.chat_input("Поставьте задачу для Kobi (поиск, генерация фото на Flux, аналитика)...")

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
        with st.status("Запуск агента...", expanded=True) as status:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=MASTER_API_KEY,
            )
            
            system_prompt = (
                "Ты — Kobi, коммерческий ИИ-агент высшего класса.\n"
                "Инструменты:\n"
                "- search_web: поиск информации и ссылок.\n"
                "- generate_image: создание фото на Flux.1 через официальный API OpenRouter.\n"
                "- execute_python_code: вычисления и работа с файлами."
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
                # --- ЛОГИКА МУЛЬТИ-МОДЕЛЬНОГО КОНСЕНСУСА ---
                if model_choice == "ensemble":
                    status.update(label="👑 [Консенсус]: Параллельный запрос к DeepSeek, Claude, GPT-4o и Gemini...", state="running")
                    
                    target_models = [
                        ("DeepSeek", "deepseek/deepseek-chat"),
                        ("Claude 3.5", "anthropic/claude-3.5-sonnet"),
                        ("GPT-4o Mini", "openai/gpt-4o-mini"),
                        ("Gemini 2.0", "google/gemini-2.0-flash-exp")
                    ]

                    def query_model(m_tuple):
                        m_label, m_id = m_tuple
                        try:
                            res = client.chat.completions.create(
                                model=m_id,
                                messages=api_messages,
                                tools=tools,
                                tool_choice="auto"
                            )
                            return m_label, res.choices[0].message
                        except Exception as ex:
                            return m_label, None

                    responses_map = {}
                    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                        futures = [executor.submit(query_model, tm) for tm in target_models]
                        for f in concurrent.futures.as_completed(futures):
                            label, msg = f.result()
                            if msg:
                                responses_map[label] = msg

                    tool_call_msg = None
                    for label, msg in responses_map.items():
                        if msg and msg.tool_calls:
                            tool_call_msg = msg
                            break

                    if tool_call_msg:
                        response_message = tool_call_msg
                    else:
                        status.update(label="👑 [Консенсус]: Мастер-синтез лучших идей всех моделей...", state="running")
                        opinions_text = "\n\n".join([
                            f"--- Вариант от {lbl} ---\n{msg.content if msg.content else 'Нет ответа'}"
                            for lbl, msg in responses_map.items()
                        ])

                        synthesis_prompt = (
                            f"Ниже приведены ответы 4-х разных моделей ИИ на запрос пользователя:\n\n{opinions_text}\n\n"
                            "ЗАДАЧА: Проанализируй все 4 ответа, убери ошибки и галлюцинации, объедини лучшие мысли "
                            "и дай один ИДЕАЛЬНЫЙ, экспертный и исчерпывающий ответ."
                        )

                        synth_messages = api_messages + [{"role": "user", "content": synthesis_prompt}]
                        synth_res = client.chat.completions.create(
                            model="deepseek/deepseek-chat",
                            messages=synth_messages
                        )
                        response_message = synth_res.choices[0].message

                else:
                    res = client.chat.completions.create(
                        model=model_choice,
                        messages=api_messages,
                        tools=tools,
                        tool_choice="auto"
                    )
                    response_message = res.choices[0].message

                # --- ОБРАБОТКА ВЫЗОВА ИНСТРУМЕНТОВ ---
                if response_message.tool_calls:
                    status.update(label="Агент выполняет инструменты (Flux / Search / Code)...", state="running")
                    
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
                                if isinstance(out_json, dict) and out_json.get("file_path"):
                                    latest_file_path = out_json["file_path"]
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

                    status.update(label="Завершение генерации результата...", state="running")
                    
                    second_response = client.chat.completions.create(
                        model="deepseek/deepseek-chat" if model_choice == "ensemble" else model_choice,
                        messages=api_messages
                    )
                    final_reply = second_response.choices[0].message.content
                else:
                    final_reply = response_message.content

                if model_choice == "ensemble":
                    final_reply = f"👑 **[Результат Мульти-Модельного Синтеза DeepSeek + Claude + GPT-4o + Gemini]**\n\n{final_reply}"

            except Exception as e:
                st.error(f"⚠️ Ошибка выполнения: {e}")
                st.stop()

            status.update(label="Готово!", state="complete", expanded=False)

        st.markdown(final_reply)
        
        assistant_item = {"role": "assistant", "content": final_reply}
        if latest_file_path and os.path.exists(latest_file_path):
            assistant_item["file_path"] = latest_file_path
            if latest_file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                st.image(latest_file_path, caption="Генерация OpenRouter FLUX.1")
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
