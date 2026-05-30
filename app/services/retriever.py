"""
Semantic search over the Bible.

When a question doesn't name a specific verse, we ask ChromaDB for the verses
whose meaning is closest to the question. The embedding model and the vector
store are both built once and cached, since they're expensive to spin up.
"""
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import settings


@lru_cache(maxsize=1)
def get_embeddings():
    """The model that turns text into vectors (loaded once, then reused)."""
    return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_vectorstore():
    """The Chroma collection of verse embeddings on disk (the ingestion script fills it)."""
    return Chroma(
        collection_name=settings.CHROMA_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=settings.CHROMA_DB_PATH,
    )


def _to_verse_doc(doc) -> dict:
    """Flatten a Chroma result into the plain {book, chapter, verse, text} dict we use everywhere."""
    meta = doc.metadata or {}
    return {
        "book": meta.get("book"),
        "chapter": meta.get("chapter"),
        "verse": meta.get("verse"),
        "text": doc.page_content,
    }


def search(query: str, k: int = settings.TOP_K) -> list:
    """Return the k verses most similar in meaning to `query`."""
    results = get_vectorstore().similarity_search(query, k=k)
    return [_to_verse_doc(d) for d in results]
