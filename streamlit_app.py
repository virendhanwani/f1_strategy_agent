"""Streamlit entry point: uv run streamlit run streamlit_app.py."""

import asyncio
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="F1 Strategy Agent", page_icon="🏎️", layout="centered")

# Accessing secrets loads top-level Cloud secrets into the environment.
# Local development can continue using the project-root .env.
try:
    st.secrets.to_dict()
except FileNotFoundError:
    pass
load_dotenv(Path(__file__).parent / ".env")


def new_chat():
    st.session_state.history = []
    st.session_state.transcript = []


def render_message(message):
    with st.chat_message(message["role"]):
        if message.get("failed"):
            st.error(message["content"])
            st.caption("This turn was not added to the agent's memory. You can send the question again.")
        else:
            st.markdown(message["content"])


async def run_turn(question, status):
    # Import only when needed so the landing page stays lightweight.
    from agents.orchestrator import stream_chat

    rows = {}
    had_tool_error = False
    async for event in stream_chat(question, st.session_state.history):
        kind = event["type"]
        if kind == "tool_start":
            row = status.empty()
            rows[event["run_id"]] = row
            row.write(event["message"])
        elif kind in ("tool_end", "tool_error"):
            row = rows.get(event["run_id"])
            if row is None:
                row = status.empty()
            label = event["tool"].replace("_", " ").capitalize()
            if kind == "tool_error":
                had_tool_error = True
                # The final answer explains limitations; don't expose raw tool errors.
                row.warning(f"{label}: some data could not be retrieved.")
            else:
                row.write(f"✓ {label}")
        elif kind == "complete":
            status.update(
                label="Finished with data limitations" if had_tool_error else "Analysis complete",
                state="complete", expanded=False,
            )
            return event
        elif kind == "error":
            status.update(label="Could not finish this question", state="error")
            return event
    status.update(label="The response ended early", state="error")
    return {"type": "error", "message": "The response ended before an answer was ready."}


if "history" not in st.session_state:
    new_chat()

with st.sidebar:
    st.title("Race strategy, explained")
    st.button("New chat", on_click=new_chat, use_container_width=True)
    st.markdown("Ask about race results, pit strategy, tyre wear, pace, or regulations.")
    st.caption("Regulation documents cover 2026 only. Detailed telemetry depends on available race data.")
    st.caption("Chat memory lasts for this browser session. Reloading or restarting the app can clear it.")
    st.subheader("Chat history")
    questions = [m["content"] for m in st.session_state.transcript if m["role"] == "user"]
    if questions:
        for number, previous_question in enumerate(questions, start=1):
            st.write(f"{number}. {previous_question}")
    else:
        st.caption("Your questions will appear here as you chat.")

st.title("🏎️ F1 Strategy Agent")
st.caption("Explore the decisions behind the race. Include a race and year to get started.")

configured = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
if not configured:
    st.info("The app needs an OpenRouter API key. Set OPENROUTER_API_KEY in .env locally or in Streamlit Cloud Secrets, then restart the app.")

example = None
if not st.session_state.transcript:
    st.markdown("**Try a question**")
    for prompt in (
        "Summarize the results of the 2023 Monaco Grand Prix.",
        "Compare Verstappen and Alonso's race pace at Monaco in 2023.",
        "What are the tyre compound requirements under the 2026 regulations?",
    ):
        if st.button(prompt, disabled=not configured, use_container_width=True):
            example = prompt

for message in st.session_state.transcript:
    render_message(message)

follow_up = None
if st.session_state.history and not st.session_state.transcript[-1].get("failed"):
    st.markdown("**Continue this conversation**")
    st.caption("Choose a follow-up or type your own below. Earlier messages stay above.")
    for prompt in (
        "Explain that in simpler terms.",
        "What data supports that explanation?",
        "What are the limitations of that analysis?",
    ):
        if st.button(prompt, disabled=not configured, use_container_width=True):
            follow_up = prompt

question = st.chat_input(
    "Ask a follow-up about this conversation…" if st.session_state.history else "Ask about an F1 race…",
    disabled=not configured,
)
question = (question or example or follow_up or "").strip()
if question:
    user_message = {"role": "user", "content": question}
    st.session_state.transcript.append(user_message)
    render_message(user_message)
    with st.chat_message("assistant"):
        with st.status("Analysing your question…", expanded=True) as status:
            try:
                result = asyncio.run(run_turn(question, status))
            except Exception:
                # Covers setup failures outside the graph's error handling.
                import logging
                logging.getLogger(__name__).exception("Chat request failed")
                status.update(label="Could not finish this question", state="error")
                result = {"type": "error", "message": "The request could not be completed. Please try again later."}
        if result["type"] == "complete":
            st.session_state.history = result["state"]["messages"]
            # BaseMessage.text supports both string and structured text content.
            answer = st.session_state.history[-1].text
            reply = {"role": "assistant", "content": answer}
            st.markdown(answer)
        else:
            reply = {"role": "assistant", "content": result["message"], "failed": True}
            st.error(reply["content"])
            st.caption("This turn was not added to the agent's memory. You can send the question again.")
        st.session_state.transcript.append(reply)
    # Rebuild the page from saved messages so history and follow-up controls
    # appear immediately after the first answer, without another user action.
    st.rerun()
