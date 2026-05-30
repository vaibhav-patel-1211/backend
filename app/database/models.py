"""
The two database tables.

A Chat is one conversation; a Message is a single turn inside it. Delete a Chat
and its Messages go with it.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database.database import Base


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, default="New Chat")
    denomination = Column(String, default="Protestant")
    created_at = Column(DateTime, default=datetime.utcnow)
    # Bumped automatically every time the row changes.
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # cascade + delete-orphan means deleting a chat also deletes its messages.
    messages = relationship(
        "Message", back_populates="chat", cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    role = Column(String)  # "user" or "assistant"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    chat = relationship("Chat", back_populates="messages")
