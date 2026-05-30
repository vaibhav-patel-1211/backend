"""
One-time setup: load the Bible into ChromaDB so semantic search works.

The pipeline is small and linear:

    bible.json  ->  validate/clean  ->  one document per verse
                ->  embed (all-MiniLM-L6-v2)  ->  store in ChromaDB

Each verse becomes its own document on purpose - we want search to return exact
verses, not big chunks. Run it from the backend/ folder:

    python -m app.ingestion.ingest_bible
"""
import json

from langchain_core.documents import Document

from app.config import settings
from app.ingestion.validator import validate_all
from app.services.retriever import get_vectorstore

BATCH_SIZE = 1000  # how many verses to embed/store at a time


def load_records():
    """Read the raw verse list from bible.json (utf-8-sig handles a stray BOM)."""
    with open(settings.BIBLE_PATH, encoding="utf-8-sig") as f:
        return json.load(f)


def build_documents(records):
    """Turn each clean verse into a LangChain Document, keeping the reference as metadata."""
    return [
        Document(
            page_content=r["text"],
            metadata={"book": r["book"], "chapter": r["chapter"], "verse": r["verse"]},
        )
        for r in records
    ]


def _store_in_batches(store, docs):
    """Embed and save the documents a batch at a time.

    The id is "Book_Chapter_Verse", so re-running the script overwrites verses
    instead of piling up duplicates.
    """
    for start in range(0, len(docs), BATCH_SIZE):
        batch = docs[start : start + BATCH_SIZE]
        ids = [f"{d.metadata['book']}_{d.metadata['chapter']}_{d.metadata['verse']}" for d in batch]
        store.add_documents(batch, ids=ids)
        print(f"  stored {min(start + BATCH_SIZE, len(docs))}/{len(docs)}")


def ingest():
    """Run the whole pipeline and report progress as it goes."""
    print(f"Loading Bible from {settings.BIBLE_PATH} ...")
    records = load_records()
    print(f"  {len(records)} raw records")

    print("Validating + normalizing ...")
    valid, errors = validate_all(records)
    print(f"  {len(valid)} valid, {len(errors)} invalid")
    # Show a handful of failures so problems are easy to spot, without spamming.
    for idx, reason in errors[:10]:
        print(f"    [skip] record {idx}: {reason}")

    docs = build_documents(valid)
    print(f"Embedding + storing {len(docs)} verses with '{settings.EMBEDDING_MODEL}' ...")
    _store_in_batches(get_vectorstore(), docs)

    print(f"Done. ChromaDB persisted at: {settings.CHROMA_DB_PATH}")


if __name__ == "__main__":
    ingest()
