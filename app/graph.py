"""
The LangGraph "brain" of the assistant.

Every message flows through this graph. The picture below is the whole story:

  user message
      -> guardrail            (is this safe to answer at all?)
      -> intent               (do they want an image or text?)
           |
   image --+-- text
     |          |
  Gemini    load history + denomination, then figure out the question type
                 |
        reference? --+-- otherwise
            |             |
     direct lookup   semantic search (ChromaDB)
            |             |
            +------+------+
                   |
            build the prompt
                   |
              ChatNVIDIA
                   |
         check the citations are real
                   |
                 (done)

Each function below is one node. Nodes only return the keys they change and
LangGraph merges them into the shared state (see state.py).
"""
import re

from langgraph.graph import END, START, StateGraph

from app.prompts import REFUSAL_MESSAGE
from app.services import (
    chat_history,
    citation_validator,
    denomination_handler,
    guardrails,
    image_generator,
    prompt_builder,
    retriever,
    verse_lookup,
)
from app.services.llm import get_llm
from app.state import GraphState

# A message counts as an image request if it says something like "generate an
# image of ..." or "picture of ...". Anything else is treated as a text question.
_IMAGE_KEYWORDS = re.compile(
    r"\b(generate|create|make|draw|paint|show me|design)\b.{0,20}\b(image|picture|photo|art|artwork|illustration|drawing|painting|depiction)\b"
    r"|\b(image|picture|illustration|drawing|painting) of\b",
    re.IGNORECASE,
)


# --------------------------- nodes ---------------------------

def guardrail_node(state: GraphState) -> dict:
    """First gate: if the request is unsafe, refuse now and skip everything else."""
    safe, _ = guardrails.is_safe(state["user_message"])
    if not safe:
        return {"blocked": True, "response": REFUSAL_MESSAGE, "citations": [], "intent": "text"}
    return {"blocked": False}


def intent_node(state: GraphState) -> dict:
    """Decide whether the user wants an image or a text answer."""
    intent = "image" if _IMAGE_KEYWORDS.search(state["user_message"]) else "text"
    return {"intent": intent}


def image_node(state: GraphState) -> dict:
    """Ask Gemini for an image. On failure we just pass the error back as the reply."""
    result = image_generator.generate_image(state["user_message"])
    if "error" in result:
        return {"response": result["error"], "image_url": None, "citations": []}
    return {
        "image_url": result["image_url"],
        "response": f"Here is an image based on your request.\n\nPrompt used: {result['prompt']}",
        "citations": [],
    }


def load_context_node(state: GraphState) -> dict:
    """Gather everything we need before answering: past messages, the user's
    denomination, and whether the question names a specific verse."""
    chat_id = state.get("chat_id")
    history = chat_history.get_history(int(chat_id)) if chat_id else []

    # We already saved the current message before running the graph, so it sits
    # at the end of the history. Drop it so we don't show it to the model twice.
    if history and history[-1].get("role") == "user" and history[-1].get("content") == state["user_message"]:
        history = history[:-1]

    # Prefer the denomination sent with this message; fall back to the chat's saved one.
    denomination = denomination_handler.normalize(
        state.get("denomination") or (chat_history.get_denomination(int(chat_id)) if chat_id else "Protestant")
    )

    # If the message mentions something like "John 3:16" we can look it up exactly;
    # otherwise we'll fall back to semantic search.
    references = verse_lookup.parse_references(state["user_message"])
    query_type = "reference" if references else "semantic"

    return {
        "chat_history": history,
        "denomination": denomination,
        "references": references,
        "query_type": query_type,
    }


def verse_lookup_node(state: GraphState) -> dict:
    """Exact path: pull the named verses straight from the dataset (no AI guessing)."""
    docs = verse_lookup.lookup_references(state.get("references", []))
    return {"retrieved_documents": docs}


def semantic_node(state: GraphState) -> dict:
    """Fuzzy path: ask ChromaDB for the verses closest in meaning to the question."""
    docs = retriever.search(state["user_message"])
    return {"retrieved_documents": docs}


def prompt_builder_node(state: GraphState) -> dict:
    """Stitch the system prompt, scripture, history and question into one message list."""
    return {"prompt_messages": prompt_builder.build_messages(state)}


async def generate_node(state: GraphState) -> dict:
    """Run the question through ChatNVIDIA.

    We use ainvoke here — the actual token streaming happens at the graph level
    via astream_events, which intercepts the LLM's internal streaming and emits
    on_chat_model_stream events for each token.
    """
    result = await get_llm().ainvoke(state["prompt_messages"])
    return {"response": result.content}


def citation_node(state: GraphState) -> dict:
    """Last safety net: drop any verse reference the model made up."""
    cleaned, citations = citation_validator.validate_response(state.get("response", ""))
    return {"response": cleaned, "citations": citations}


# --------------------------- routing ---------------------------
# These tiny functions just answer "where do we go next?" for the forks above.

def route_after_guardrail(state: GraphState) -> str:
    """Blocked requests stop here; safe ones move on to intent detection."""
    return END if state.get("blocked") else "classify_intent"


def route_after_intent(state: GraphState) -> str:
    """Send image requests to Gemini, everything else down the text path."""
    return "image" if state.get("intent") == "image" else "load_context"


def route_after_context(state: GraphState) -> str:
    """Named verse -> exact lookup; open question -> semantic search."""
    return "verse_lookup" if state.get("query_type") == "reference" else "semantic"


# --------------------------- build ---------------------------

def build_graph():
    """Connect the nodes in the order shown in the diagram and compile the graph."""
    g = StateGraph(GraphState)
    g.add_node("guardrail", guardrail_node)
    g.add_node("classify_intent", intent_node)
    g.add_node("image", image_node)
    g.add_node("load_context", load_context_node)
    g.add_node("verse_lookup", verse_lookup_node)
    g.add_node("semantic", semantic_node)
    g.add_node("prompt_builder", prompt_builder_node)
    g.add_node("generate", generate_node)
    g.add_node("citation", citation_node)

    g.add_edge(START, "guardrail")
    # guardrail either ends the run (blocked) or continues to intent.
    g.add_conditional_edges("guardrail", route_after_guardrail, {"classify_intent": "classify_intent", END: END})
    # intent splits the flow into the image branch and the text branch.
    g.add_conditional_edges("classify_intent", route_after_intent, {"image": "image", "load_context": "load_context"})
    g.add_edge("image", END)
    # text branch picks exactly one of the two retrieval styles...
    g.add_conditional_edges("load_context", route_after_context, {"verse_lookup": "verse_lookup", "semantic": "semantic"})
    # ...and both rejoin at the prompt builder.
    g.add_edge("verse_lookup", "prompt_builder")
    g.add_edge("semantic", "prompt_builder")
    g.add_edge("prompt_builder", "generate")
    g.add_edge("generate", "citation")
    g.add_edge("citation", END)
    return g.compile()


# Built once at import time and reused for every request.
graph = build_graph()
