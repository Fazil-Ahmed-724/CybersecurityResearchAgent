import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000/chat"

st.set_page_config(
    page_title="Cybersecurity Research Agent",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Cybersecurity Research Agent")

# --------------------------------------------------
# Session State
# --------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# --------------------------------------------------
# Sidebar
# --------------------------------------------------

with st.sidebar:

    st.header("Question History")

    if st.button("🗑️ Clear Chat"):

        st.session_state.messages = []
        st.rerun()

    questions = [
        msg["content"]
        for msg in st.session_state.messages
        if msg["role"] == "user"
    ]

    for q in reversed(questions[-10:]):

        st.caption(
            "🧑 " + q[:60]
        )

# --------------------------------------------------
# Render Existing Messages
# --------------------------------------------------

for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):

        st.markdown(
            msg["content"]
        )

        if (
            msg["role"] == "assistant"
            and "sources" in msg
        ):

            st.divider()

            st.subheader(
                "Sources"
            )

            for source in msg["sources"]:

                st.markdown(
                    f"### {source['source']}"
                )

                st.write(
                    source["title"]
                )

                if source["url"]:

                    st.link_button(
                        "🔗 Open Article",
                        source["url"]
                    )

# --------------------------------------------------
# Chat Input
# --------------------------------------------------

question = st.chat_input(
    "Ask a cybersecurity question..."
)

# --------------------------------------------------
# Ask Question
# --------------------------------------------------

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
                API_URL,
                json={
                    "question": question
                },
                timeout=120
            )

        if response.status_code == 200:

            data = response.json()

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": data["answer"],
                    "sources": data["sources"]
                }
            )

        else:

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"API Error: {response.status_code}"
                }
            )

    except Exception as e:

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"Error: {str(e)}"
            }
        )

    st.rerun()