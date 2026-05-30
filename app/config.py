"""
All the knobs in one place.

Reads settings from the environment (with a .env file as a convenience) so we
never hard-code keys or paths. Import `settings` anywhere you need them. Paths
are relative to the backend/ folder you run uvicorn from.
"""
import os

from dotenv import load_dotenv

# Pull in a .env file if there is one. Real environment variables still win.
load_dotenv()


class Settings:
    # Keys for the two external services we call.
    NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Where things live on disk.
    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "app/chroma_db")
    SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "app/database/chat.db")
    BIBLE_PATH = os.getenv("BIBLE_PATH", "app/data/bible.json")
    IMAGE_DIR = os.getenv("IMAGE_DIR", "app/static/images")

    # Which models to use (overridable, with sensible defaults).
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "openai/gpt-oss-120b")
    GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-preview-image-generation")

    # Retrieval settings.
    CHROMA_COLLECTION = "bible_verses"
    TOP_K = 5  # how many verses semantic search returns

    # The traditions we explicitly support.
    DENOMINATIONS = ["Catholic", "Protestant", "Orthodox"]


settings = Settings()
