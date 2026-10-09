import os
import streamlit as st
from chat_requests import generate_response

st.set_page_config(
    page_title="QuantumHound Chatbot",
    page_icon=":stopwatch:",
    initial_sidebar_state="collapsed",
)
st.markdown("# :stopwatch: :dog: QuantumHound Chatbot")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app reload
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input
if prompt := st.chat_input("What can I help you with today?"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display chatbot responses in chat message container
    with st.chat_message("assistant"):
        with st.spinner("Considering your request..."):
            response = generate_response(prompt)

        if response["success"]:
            st.write(response["message"])
            message_content = response["message"]
            is_error = False
        else:
            st.error(response["error"])
            message_content = response["error"]
            is_error = True

        # Add chatbot response to chat history
        message_dict = {
            "role": "assistant",
            "content": message_content,
            "is_error": is_error,
        }
        st.session_state.messages.append(message_dict)
