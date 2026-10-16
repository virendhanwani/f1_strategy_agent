"""Offline UI checks. Run: uv run python -m tests.test_streamlit_ui."""

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from streamlit.testing.v1 import AppTest


def main():
    path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    app = AppTest.from_file(str(path)).run()
    assert not app.exception
    assert len(app.chat_input) == 1
    assert app.session_state.history == []

    # Seed an existing conversation without calling a model or data provider.
    app.session_state.history = [HumanMessage("Hello"), AIMessage("Welcome")]
    app.session_state.transcript = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Welcome"},
        {"role": "assistant", "content": "The request timed out.", "failed": True},
    ]
    app.run()
    assert not app.exception
    assert len(app.chat_message) == 3
    assert app.error[0].value == "The request timed out."
    assert len(app.session_state.history) == 2

    app.session_state.transcript.pop()  # Return to the last successful answer.
    app.run()
    assert len(app.chat_message) == 2
    assert any(button.label == "Explain that in simpler terms." for button in app.button)
    assert "follow-up" in app.chat_input[0].placeholder
    assert any(item.value == "1. Hello" for item in app.sidebar.markdown)
    app.run()  # Ordinary reruns must preserve the visible conversation.
    assert len(app.chat_message) == 2
    assert len(app.session_state.history) == 2

    other = AppTest.from_file(str(path)).run()
    assert other.session_state.history == []
    assert other.session_state.transcript == []

    # Simulate a script rerun after saving a question but before saving a reply.
    app.session_state.transcript.append({"role": "user", "content": "Interrupted question"})
    app.run()
    assert not app.exception
    assert app.session_state.transcript[-1]["failed"]
    assert "interrupted" in app.error[0].value
    assert len(app.session_state.history) == 2
    count = len(app.session_state.transcript)
    app.run()
    assert len(app.session_state.transcript) == count

    next(button for button in app.button if button.label == "New chat").click().run()
    assert not app.exception
    assert app.session_state.history == []
    assert app.session_state.transcript == []
    assert len(app.chat_message) == 0
    print("UI checks passed: rendering, failure display, session isolation, and reset.")


if __name__ == "__main__":
    main()
