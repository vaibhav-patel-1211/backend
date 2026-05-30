"""
The SQLite plumbing: the engine, a session factory, and table setup.

Everything else imports `Base` to define models, `init_db()` to create the
tables on startup, and `get_session()` to talk to the database.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# Make sure the folder for the .db file exists before SQLite tries to open it.
os.makedirs(os.path.dirname(settings.SQLITE_DB_PATH) or ".", exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.SQLITE_DB_PATH}",
    # FastAPI may use the connection from different threads; SQLite blocks that
    # by default, so we turn the check off.
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Create the tables. Importing models first registers them on Base."""
    from app.database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_session():
    """Hand out a new session. Whoever opens it is responsible for closing it."""
    return SessionLocal()
