"""
The shared "clipboard" that every graph node reads from and writes to.

It's a TypedDict with total=False, which just means a node can return only the
fields it cares about and LangGraph merges them in. The first group is the data
we actually answer with; the second group is bookkeeping the nodes use to decide
where to go next.
"""
from typing import List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    # --- the conversation ---
    user_message: str               # what the user just asked
    chat_id: str                    # which conversation this belongs to
    denomination: str               # Catholic | Protestant | Orthodox
    intent: str                     # "image" or "text"
    retrieved_documents: List[dict]  # verses we pulled, [{book, chapter, verse, text}]
    response: str                   # the assistant's reply
    image_url: Optional[str]        # only set when we generated an image
    citations: List[str]            # verified references, e.g. ["John 3:16"]
    chat_history: List[dict]        # earlier turns, [{role, content}]

    # --- internal bookkeeping ---
    blocked: bool           # guardrail tripped, so we refuse
    query_type: str         # "reference" (named verse) or "semantic" (open question)
    references: List[dict]  # verses named in the message, {book, chapter, verse}
    prompt_messages: list   # the final message list we hand to the LLM
