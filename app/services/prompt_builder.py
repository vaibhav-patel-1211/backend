"""
Assemble the prompt we send to the model.

The model only ever sees what we put here, so this is where we glue together the
ground rules (system prompt), the user's denomination, the verses we retrieved,
the earlier conversation, and finally the new question.
"""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.prompts import NO_CONTEXT_NOTE, SYSTEM_PROMPT
from app.services import denomination_handler

DEFAULT_DENOMINATION = "Protestant"
# Tells the model these are the only verses it's allowed to quote.
_SCRIPTURE_HEADER = "Retrieved scripture (only cite verses listed here):"


def _format_scripture(docs: list) -> str:
    """Render the retrieved verses as a citable block (or a note if we found none)."""
    if not docs:
        return NO_CONTEXT_NOTE
    lines = [_SCRIPTURE_HEADER]
    lines += [f"({d['book']} {d['chapter']}:{d['verse']}) {d['text']}" for d in docs]
    return "\n".join(lines)


def _history_messages(history: list) -> list:
    """Turn our stored {role, content} turns into the Human/AI messages LangChain expects."""
    messages = []
    for turn in history:
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=turn["content"]))
        elif turn.get("role") == "assistant":
            messages.append(AIMessage(content=turn["content"]))
    return messages


def build_messages(state) -> list:
    """Build the full message list: system rules first, the new question last."""
    denomination = state.get("denomination", DEFAULT_DENOMINATION)
    docs = state.get("retrieved_documents", [])

    # The system message carries the rules, the denomination lens, and the verses.
    system = (
        f"{SYSTEM_PROMPT}\n\n"
        f"DENOMINATION CONTEXT: {denomination_handler.get_context(denomination)}\n\n"
        f"{_format_scripture(docs)}"
    )

    return [
        SystemMessage(content=system),
        *_history_messages(state.get("chat_history", [])),
        HumanMessage(content=state["user_message"]),
    ]
