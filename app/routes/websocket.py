"""
The live chat connection.

This is what the frontend talks to. The browser opens one WebSocket and, for
each message, sends:

    {"chat_id": 1, "message": "What does Romans 8:28 mean?", "denomination": "Protestant"}

and we send back a little stream of events:

    {"type": "chat",  "chat_id": 1}            # which chat this ended up in
    {"type": "token", "content": "..."}        # answer text, a few letters at a time
    {"type": "image", "image_url": "..."}      # for picture requests
    {"type": "done",  "response": "...", "citations": [...]}
    {"type": "error", "message": "..."}

We run the LangGraph with `astream_events` so we can forward the model's tokens
as they're produced while still grabbing the final state at the end (for the
citations or the image URL).
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.graph import graph
from app.services import chat_history, denomination_handler

router = APIRouter()

# The two streaming events we care about out of everything LangGraph emits.
_EVENT_TOKEN = "on_chat_model_stream"   # the model produced a chunk of text
_EVENT_CHAIN_END = "on_chain_end"       # something finished (a node, or the whole graph)


async def _run_graph(ws: WebSocket, state: dict) -> dict:
    """Run the graph, push tokens to the browser as they arrive, return the final state."""
    final_state = {}
    streamed = ""  # everything the model streamed, kept as a backup answer
    async for event in graph.astream_events(state, version="v2"):
        kind = event["event"]
        if kind == _EVENT_TOKEN:
            token = event["data"]["chunk"].content
            if token:
                streamed += token
                await ws.send_json({"type": "token", "content": token})
        elif kind == _EVENT_CHAIN_END:
            output = event["data"].get("output")
            # Lots of things emit on_chain_end; only the whole graph's output
            # carries user_message, so that's how we spot the real final state.
            if isinstance(output, dict) and "user_message" in output:
                final_state = output
    # If the graph never set a response, fall back to whatever we streamed.
    final_state.setdefault("response", streamed)
    return final_state


async def _finalize(ws: WebSocket, chat_id: int, final_state: dict) -> None:
    """Save the assistant's reply and send the closing event(s)."""
    image_url = final_state.get("image_url")
    if image_url:
        await ws.send_json({"type": "image", "image_url": image_url})
        chat_history.add_message(chat_id, "assistant", image_url)
        await ws.send_json({"type": "done", "response": final_state.get("response", ""), "citations": []})
        return

    # Text answer: send the citation-checked version (not the raw streamed text).
    response = final_state.get("response", "")
    citations = final_state.get("citations", [])
    chat_history.add_message(chat_id, "assistant", response)
    await ws.send_json({"type": "done", "response": response, "citations": citations})


@router.websocket("/ws/chat")
async def chat_ws(ws: WebSocket):
    """One open connection; we loop, handling one message per round trip."""
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            message = (data.get("message") or "").strip()
            denomination = denomination_handler.normalize(data.get("denomination"))

            # Nothing to do for an empty message - tell the client and wait for the next one.
            if not message:
                await ws.send_json({"type": "error", "message": "Empty message."})
                continue

            # Find (or start) the chat, save what the user said, tell them the id.
            chat_id = chat_history.ensure_chat(data.get("chat_id"), denomination)
            chat_history.add_message(chat_id, "user", message)
            await ws.send_json({"type": "chat", "chat_id": chat_id})

            state = {"user_message": message, "chat_id": str(chat_id), "denomination": denomination}
            final_state = await _run_graph(ws, state)
            await _finalize(ws, chat_id, final_state)

    except WebSocketDisconnect:
        # Browser closed the tab - nothing to clean up.
        return
    except Exception as e:  # pragma: no cover
        # Don't let the socket die silently; surface the error to the client.
        await ws.send_json({"type": "error", "message": str(e)})
