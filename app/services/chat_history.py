"""
Saving and loading conversations.

A thin wrapper over the database so the rest of the app never touches SQLAlchemy
directly. Two rules keep things simple here:

  1. Every function opens a short-lived session through `_session()` and lets it
     close automatically.
  2. We always return plain dicts, never live ORM objects, so callers don't trip
     over "this object is detached from its session" errors.
"""
from contextlib import contextmanager

from app.database.database import get_session
from app.database.models import Chat, Message
from app.services import denomination_handler

DEFAULT_DENOMINATION = "Protestant"
DEFAULT_TITLE = "New Chat"
HISTORY_LIMIT = 20  # how many past messages we feed back to the model as memory


# ─── Session helper ──────────────────────────────────────────────────────────

@contextmanager
def _session():
    """Open a DB session and make sure it's closed no matter what."""
    db = get_session()
    try:
        yield db
    finally:
        db.close()


# ─── Chats ───────────────────────────────────────────────────────────────────

def create_chat(title: str = DEFAULT_TITLE, denomination: str = DEFAULT_DENOMINATION) -> dict:
    """Create a new conversation and return it."""
    with _session() as db:
        chat = Chat(
            title=title or DEFAULT_TITLE,
            denomination=denomination_handler.normalize(denomination),
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)  # reload so we get the generated id + timestamps
        return _chat_to_dict(chat)


def list_chats() -> list:
    """Every conversation, most recently updated first."""
    with _session() as db:
        chats = db.query(Chat).order_by(Chat.updated_at.desc()).all()
        return [_chat_to_dict(c) for c in chats]


def get_chat(chat_id: int):
    """One conversation plus its messages, or None if it doesn't exist."""
    with _session() as db:
        chat = db.get(Chat, chat_id)
        if not chat:
            return None
        data = _chat_to_dict(chat)
        data["messages"] = [_message_to_dict(m) for m in chat.messages]
        return data


def delete_chat(chat_id: int) -> bool:
    """Delete a conversation (messages go too, via cascade). True if it existed."""
    with _session() as db:
        chat = db.get(Chat, chat_id)
        if not chat:
            return False
        db.delete(chat)
        db.commit()
        return True


def rename_chat(chat_id: int, title: str):
    """Change a conversation's title; returns the updated chat, or None if missing."""
    with _session() as db:
        chat = db.get(Chat, chat_id)
        if not chat:
            return None
        chat.title = title
        db.commit()
        db.refresh(chat)
        return _chat_to_dict(chat)


# ─── Messages ────────────────────────────────────────────────────────────────

def add_message(chat_id: int, role: str, content: str):
    """Append one message (role is "user" or "assistant") to a conversation."""
    with _session() as db:
        db.add(Message(chat_id=chat_id, role=role, content=content))
        db.commit()


def get_history(chat_id: int, limit: int = HISTORY_LIMIT) -> list:
    """The last `limit` messages as [{role, content}], oldest first."""
    with _session() as db:
        # Grab the newest ones (that's what `limit` should keep)...
        msgs = (
            db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.id.desc())
            .limit(limit)
            .all()
        )
        # ...then flip back to chronological order for the model to read.
        return [{"role": m.role, "content": m.content} for m in reversed(msgs)]


# ─── Lookups / helpers ───────────────────────────────────────────────────────

def get_denomination(chat_id: int) -> str:
    """A chat's saved denomination, or the default if the chat is gone."""
    with _session() as db:
        chat = db.get(Chat, chat_id)
        return chat.denomination if chat else DEFAULT_DENOMINATION


def ensure_chat(chat_id, denomination: str = DEFAULT_DENOMINATION):
    """Return a chat id we can use - the given one if it exists, otherwise a new chat."""
    if chat_id:
        with _session() as db:
            if db.get(Chat, int(chat_id)):
                return int(chat_id)
    return create_chat(denomination=denomination)["id"]


# Timestamps become ISO strings so the dicts are JSON-friendly out of the box.

def _chat_to_dict(chat: Chat) -> dict:
    return {
        "id": chat.id,
        "title": chat.title,
        "denomination": chat.denomination,
        "created_at": chat.created_at.isoformat() if chat.created_at else None,
        "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
    }


def _message_to_dict(m: Message) -> dict:
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "timestamp": m.timestamp.isoformat() if m.timestamp else None,
    }
