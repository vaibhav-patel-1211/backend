"""
Plain REST endpoints for managing conversations (create, list, read, delete,
rename). The real work lives in the chat_history service; here we just handle
the request shapes and turn "not found" into a 404.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import chat_history

router = APIRouter(prefix="/chat", tags=["chats"])

_NOT_FOUND = "Chat not found"


class NewChatRequest(BaseModel):
    title: str = "New Chat"
    denomination: str = "Protestant"


class RenameRequest(BaseModel):
    title: str


@router.post("/new")
def new_chat(req: NewChatRequest):
    """Start a fresh conversation."""
    return chat_history.create_chat(req.title, req.denomination)


@router.get("/list")
def list_chats():
    """All conversations, newest first."""
    return chat_history.list_chats()


@router.get("/{chat_id}")
def get_chat(chat_id: int):
    """One conversation with its messages (404 if it's gone)."""
    chat = chat_history.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return chat


@router.delete("/{chat_id}")
def delete_chat(chat_id: int):
    """Delete a conversation and its messages."""
    if not chat_history.delete_chat(chat_id):
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return {"deleted": chat_id}


@router.patch("/{chat_id}/rename")
def rename_chat(chat_id: int, req: RenameRequest):
    """Give a conversation a new title."""
    chat = chat_history.rename_chat(chat_id, req.title)
    if not chat:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return chat
