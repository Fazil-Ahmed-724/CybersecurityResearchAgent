import sys
from pathlib import Path

import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.answer_cleanup import clean_generated_answer

BASE_URL = "http://127.0.0.1:8000"


def unique_sources(sources):
    unique = []
    seen = set()

    for source in sources or []:
        source_key = (
            source.get("url")
            or source.get("title")
            or source.get("source")
            or ""
        )
        source_key = source_key.strip().lower()

        if not source_key:
            continue

        if source_key in seen:
            continue

        seen.add(source_key)
        unique.append(source)

    return unique


def normalize_message(msg: dict) -> dict:
    return {
        "role": msg.get("role", ""),
        "content": msg.get("content", ""),
        "sources": unique_sources(msg.get("sources", [])),
    }


def load_chat_messages(chat_id: int, headers: dict) -> list[dict]:
    response = requests.get(
        f"{BASE_URL}/chats/{chat_id}/messages",
        headers=headers,
        timeout=30
    )

    if response.status_code != 200:
        raise RuntimeError(f"Failed to load chat messages: {response.status_code}")

    raw_messages = response.json()
    normalized = []

    for msg in raw_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        metadata = msg.get("metadata_json") or {}
        sources = []

        if role == "assistant":
            sources = metadata.get("sources", []) or []

        normalized.append(
            normalize_message(
                {
                    "role": role,
                    "content": content,
                    "sources": sources,
                }
            )
        )

    return normalized


# ----------------------------------
# Page Config
# ----------------------------------

st.set_page_config(
    page_title="Cybersecurity Research Agent",
    page_icon="🛡️",
    layout="wide"
)

# ----------------------------------
# Session State
# ----------------------------------

defaults = {
    "token": None,
    "user_id": None,
    "user_name": None,
    "messages": [],
    "chat_id": None,
    "history_refresh": True
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ----------------------------------
# Login / Register
# ----------------------------------

if not st.session_state.token:
    st.title("🛡️ Cybersecurity Research Agent")

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={
                    "email": email,
                    "password": password
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                st.session_state.token = data["access_token"]
                st.session_state.user_id = data["user_id"]
                st.session_state.user_name = data["name"]

                st.session_state.chat_id = None
                st.session_state.messages = []
                st.session_state.history_refresh = True

                st.success("Login successful")
                st.rerun()
            else:
                st.error("Invalid credentials")

    with register_tab:
        name = st.text_input("Name")
        reg_email = st.text_input("Email", key="register_email")
        reg_password = st.text_input("Password", type="password", key="register_password")

        if st.button("Register", use_container_width=True):
            response = requests.post(
                f"{BASE_URL}/auth/register",
                json={
                    "name": name,
                    "email": reg_email,
                    "password": reg_password
                },
                timeout=30
            )

            if response.status_code == 200:
                st.success("Registration successful")
            else:
                st.error(response.text)

    st.stop()

# ----------------------------------
# Auth Header
# ----------------------------------

headers = {
    "Authorization": f"Bearer {st.session_state.token}"
}

# ----------------------------------
# Load User Chats
# ----------------------------------

user_chats = []

try:
    history_response = requests.get(
        f"{BASE_URL}/chats/my-chats",
        headers=headers,
        timeout=10
    )

    if history_response.status_code == 200:
        user_chats = history_response.json()
        user_chats = sorted(
            user_chats,
            key=lambda x: x["id"],
            reverse=True
        )

except Exception as ex:
    st.sidebar.error(str(ex))

# ----------------------------------
# Main UI
# ----------------------------------

st.title("🛡️ Cybersecurity Research Agent")

# ----------------------------------
# Sidebar
# ----------------------------------

with st.sidebar:
    st.header(f"👤 {st.session_state.user_name}")
    st.caption(f"Chats Found: {len(user_chats)}")

    if st.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.divider()
    st.header("Question History")

    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.chat_id = None
        st.session_state.messages = []
        st.session_state.history_refresh = True
        st.rerun()

    for chat in user_chats:
        title = chat["title"]

        if len(title) > 30:
            title = title[:30] + "..."

        display_title = (
            f"#{chat['id']} | "
            f"{title} "
            f"({chat['created_at'][:10]})"
        )

        if st.button(
            display_title,
            key=f"history_{chat['id']}",
            use_container_width=True
        ):
            try:
                st.session_state.chat_id = chat["id"]
                st.session_state.messages = load_chat_messages(chat["id"], headers)
                st.session_state.history_refresh = False
                st.rerun()
            except Exception as ex:
                st.error(str(ex))

# ----------------------------------
# Chat Messages
# ----------------------------------

for msg_index, msg in enumerate(st.session_state.messages):
    msg = normalize_message(msg)

    with st.chat_message(msg["role"]):
        content = msg["content"]

        if msg["role"] == "assistant":
            content = clean_generated_answer(content)

        st.markdown(content)

        if msg["role"] == "assistant":
            sources = unique_sources(msg.get("sources", []))

            if sources:
                st.divider()
                st.subheader("Sources")

                for source_index, source in enumerate(sources):
                    st.markdown(f"### {source.get('source', 'Unknown')}")
                    st.write(source.get("title", "Untitled"))

                    if source.get("url"):
                        st.link_button(
                            "🔗 Open Article",
                            source["url"],
                            key=f"src_{msg_index}_{source_index}"
                        )

# ----------------------------------
# Ask Question
# ----------------------------------

question = st.chat_input("Ask a cybersecurity question...")

if question:
    st.session_state.messages.append(
        normalize_message(
            {
                "role": "user",
                "content": question,
                "sources": []
            }
        )
    )

    try:
        with st.spinner("Researching..."):
            response = requests.post(
                f"{BASE_URL}/chat",
                json={
                    "question": question,
                    "chat_id": st.session_state.chat_id
                },
                headers=headers,
                timeout=120
            )

        if response.status_code == 200:
            data = response.json()

            if "chat_id" in data:
                st.session_state.chat_id = data["chat_id"]
                st.session_state.history_refresh = True

            st.session_state.messages.append(
                normalize_message(
                    {
                        "role": "assistant",
                        "content": data.get("answer", ""),
                        "sources": data.get("sources", []),
                    }
                )
            )

            st.rerun()

        else:
            st.error(f"API Error: {response.status_code}")
            try:
                st.error(response.text)
            except Exception:
                pass

    except Exception as ex:
        st.error(str(ex))
