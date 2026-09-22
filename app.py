import os
import io
import json
import re
import urllib.parse
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
    page_title="Kobi Supreme Agent", 
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
    st.info("💡 Стабильный режим: Мульти-модельный консенсус + Надежная генерация.")
    
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

st.title("🤖 Kobi — Мульти-агентный комплекс")
st.caption(f"Текущий чат: **{st.session_state.current_chat}**")

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
            "description": "Генерирует качественное изображение по описанию.",
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
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=MASTER_API_KEY,
        )
        response = client.chat.completions.create(
            model="meta/muse-image",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        
        img_match = re.search(r'(https?://[^\s)]+)', content)
        image_url = img_match.group(1) if img_match else content.strip()
        
        return json.dumps({"status": "success", "image_url": image_url, "prompt": prompt}, ensure_ascii=False)
    except Exception as e:
        enhanced_prompt = f"{prompt}, photorealistic, highly detailed, 8k"
        encoded = urllib.parse.quote(enhanced_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&nologo=true&seed=1337"
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
            if "image_url" in message and message["image_url"]:
                st.image(message["image_url"])
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
        with st.status("Запуск агента...", expanded=True) as status:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=MASTER_API_KEY,
            )
            
            system_prompt = (
                "Ты — Kobi, коммерческий ИИ-агент высшего класса.\n"
                "Инструменты:\n"
                "- search_web: поиск информации.\n"
                "- generate_image: генерация картинок.\n"
                "- execute_python_code: работа с кодом и файлами."
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
                if model_choice == "ensemble":
                    status.update(label="👑 [Консенсус]: Запрос к DeepSeek, Claude, GPT-4o и Gemini...", state="running")
                    
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
                        status.update(label="👑 [Консенсус]: Мастер-синтез ответов...", state="running")
                        opinions_text = "\n\n".join([
                            f"--- Вариант от {lbl} ---\n{msg.content if msg.content else 'Нет ответа'}"
                            for lbl, msg in responses_map.items()
                        ])

                        synthesis_prompt = (
                            f"Ответы 4 моделей:\n\n{opinions_text}\n\n"
                            "Сделай один идеальный экспертный ответ."
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

                if response_message.tool_calls:
                    status.update(label="Выполнение инструментов...", state="running")
                    
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

                    status.update(label="Финализация...", state="running")
                    
                    second_response = client.chat.completions.create(
                        model="deepseek/deepseek-chat" if model_choice == "ensemble" else model_choice,
                        messages=api_messages
                    )
                    final_reply = second_response.choices[0].message.content
                else:
                    final_reply = response_message.content

                if model_choice == "ensemble":
                    final_reply = f"👑 **[Мульти-Модельный Консенсус]**\n\n{final_reply}"

            except Exception as e:
                st.error(f"⚠️ Ошибка выполнения: {e}")
                st.stop()

            status.update(label="Готово!", state="complete", expanded=False)

# Авто-экстрактор картинок из текста, если модель скинула markdown-ссылку напрямую
        if not generated_image_url:
            img_match = re.search(r'!$$.*?$$$(https?://[^\s)]+)$', final_reply)
            if img_match:
generated_image_url = img_match.group(1)
# Очищаем текст от мусорных тегов картинок
    final_reply_clean = re.sub(r'!$$.*?$$$.*?$', '', final_reply).strip()
st.markdown(final_reply_clean)
    
    if generated_image_url:
        st.image(generated_image_url)

    assistant_item = {"role": "assistant", "content": final_reply_clean}
    if generated_image_url:
        assistant_item["image_url"] = generated_image_url
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
