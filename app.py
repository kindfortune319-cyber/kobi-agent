import os
import io
import json
import streamlit as st
import pandas as pd
from openai import OpenAI
from docx import Document
from duckduckgo_search import DDGS

# Настройка страницы
st.set_page_config(
    page_title="Kobi — Autonomous God-Mode Agent", 
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
    st.markdown("### 🤖 Kobi God-Mode Agent")
    st.info("💡 Активен режим коммерческого агента с чистым интерфейсом.")
    
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

st.title("🤖 Kobi — Автономный ИИ-Агент нового поколения")
st.caption(f"Текущий чат: **{st.session_state.current_chat}** | Инструменты: Web Search + Python Sandbox")

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
                        "description": "Точный поисковый запрос (например, 'FC 27 видео ютуб' или 'свежие новости ИИ')."
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# --- ИСПОЛНИТЕЛИ ---
def search_web(query: str) -> str:
    try:
        results = []
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

available_functions = {
    "search_web": search_web
}

# --- ВЫВОД ИСТОРИИ ЧАТА (ОТФИЛЬТРОВАННЫЙ, ТОЛЬКО USER И ASSISTANT) ---
for message in messages_list:
    if message["role"] in ["user", "assistant"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# --- ВХОДНЫЕ ДАННЫЕ ---
prompt = st.chat_input("Поставьте задачу для Kobi (например: найди видео в ютуб про...)")

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
        with st.status("Kobi ищет информацию в сети...", expanded=True) as status:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=MASTER_API_KEY,
            )
            
            system_prompt = (
                "Ты — Kobi, элитный коммерческий ИИ-агент нового поколения.\n"
                "Когда пользователь просит найти видео на YouTube, статьи, сайты или любую информацию, ты ОБЯЗАН использовать инструмент search_web.\n"
                "Получив результаты поиска, выбери самые релевантные ссылки и выдай пользователю КРАСИВЫЙ, оформленный ответ.\n"
                "ОБЯЗАТЕЛЬНО оформляй ссылки в виде кликабельных Markdown-ссылок прямо в тексте, например: [Название видео](https://youtube.com/...).\n"
                "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО показывать пользователю сырой JSON, технические детали, массивы скобок `[]` или отправлять его на страницы поисковиков вроде duckduckgo.com. Только чистый, готовый результат с прямыми ссылками."
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

            try:
                response = client.chat.completions.create(
                    model=model_choice,
                    messages=api_messages,
                    tools=tools,
                    tool_choice="auto"
                )
                
                response_message = response.choices[0].message
                
                if response_message.tool_calls:
                    status.update(label="Обрабатываю результаты поиска...", state="running")
                    
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

                    status.update(label="Формирую финальный ответ...", state="running")
                    
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
        messages_list.append({"role": "assistant", "content": final_reply})
        st.rerun()
        st.markdown(final_reply)
        messages_list.append({"role": "assistant", "content": final_reply})
        st.rerun()
