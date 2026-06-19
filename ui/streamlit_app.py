import requests
import streamlit as st

BASE_URL = "http://127.0.0.1:8000"


def unique_sources(sources):

    unique = []
    seen = set()

    for source in sources:

        source_key = (
            source.get("url")
            or source.get("title")
            or source.get("source")
        )

        if source_key in seen:
            continue

        seen.add(
            source_key
        )

        unique.append(
            source
        )

    return unique

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

    login_tab, register_tab = st.tabs(
        ["Login", "Register"]
    )

    with login_tab:

        email = st.text_input(
            "Email"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        if st.button(
            "Login",
            use_container_width=True
        ):

            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={
                    "email": email,
                    "password": password
                }
            )

            if response.status_code == 200:

                data = response.json()

                st.session_state.token = data["access_token"]
                st.session_state.user_id = data["user_id"]
                st.session_state.user_name = data["name"]

                st.session_state.chat_id = None
                st.session_state.messages = []
                st.session_state.history_refresh = True

                st.success(
                    "Login successful"
                )

                st.rerun()

            else:

                st.error(
                    "Invalid credentials"
                )

    with register_tab:

        name = st.text_input(
            "Name"
        )

        reg_email = st.text_input(
            "Email",
            key="register_email"
        )

        reg_password = st.text_input(
            "Password",
            type="password",
            key="register_password"
        )

        if st.button(
            "Register",
            use_container_width=True
        ):

            response = requests.post(
                f"{BASE_URL}/auth/register",
                json={
                    "name": name,
                    "email": reg_email,
                    "password": reg_password
                }
            )

            if response.status_code == 200:

                st.success(
                    "Registration successful"
                )

            else:

                st.error(
                    response.text
                )

    st.stop()

# ----------------------------------
# Auth Header
# ----------------------------------

headers = {
    "Authorization":
    f"Bearer {st.session_state.token}"
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

st.title(
    "🛡️ Cybersecurity Research Agent"
)

# ----------------------------------
# Sidebar
# ----------------------------------

with st.sidebar:

    st.header(
        f"👤 {st.session_state.user_name}"
    )

    # st.caption(
    #     f"User ID: {st.session_state.user_id}"
    # )

    st.caption(
        f"Chats Found: {len(user_chats)}"
    )

    if st.button(
        "Logout",
        use_container_width=True
    ):

        for key in list(
            st.session_state.keys()
        ):
            del st.session_state[key]

        st.rerun()

    st.divider()

    st.header(
        "Question History"
    )

    if st.button(
        "➕ New Chat",
        use_container_width=True
    ):

        st.session_state.chat_id = None
        st.session_state.messages = []

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

            response = requests.get(
                f"{BASE_URL}/chats/{chat['id']}/messages",
                headers=headers
            )

            if response.status_code == 200:

                messages = response.json()

                st.session_state.chat_id = chat["id"]

                st.session_state.messages = []

                for msg in messages:

                    st.session_state.messages.append(
                        {
                            "role": msg["role"],
                            "content": msg["content"]
                        }
                    )

                st.rerun()

# ----------------------------------
# Chat Messages
# ----------------------------------

for msg in st.session_state.messages:

    with st.chat_message(
        msg["role"]
    ):

        st.markdown(
            msg["content"]
        )

        if (
            msg["role"] == "assistant"
            and "sources" in msg
        ):

            sources = unique_sources(
                msg["sources"]
            )

            if not sources:
                continue

            st.divider()

            st.subheader(
                "Sources"
            )

            for source in sources:

                st.markdown(
                    f"### {source['source']}"
                )

                st.write(
                    source["title"]
                )

                if source.get(
                    "url"
                ):

                    st.link_button(
                        "🔗 Open Article",
                        source["url"]
                    )

# ----------------------------------
# Ask Question
# ----------------------------------

question = st.chat_input(
    "Ask a cybersecurity question..."
)

if question:

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question
        }
    )

    try:

        with st.spinner(
            "Researching..."
        ):

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
                {
                    "role": "assistant",
                    "content": data["answer"],
                    "sources": data.get(
                        "sources",
                        []
                    )
                }
            )

            st.rerun()

        else:

            st.error(
                f"API Error: {response.status_code}"
            )

    except Exception as ex:

        st.error(
            str(ex)
        )
