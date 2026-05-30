"""
App entry point - this is what `uvicorn app.main:app` runs.

It wires the pieces together: open CORS (fine for local dev), a /static mount so
generated images are downloadable, the three routers, and a couple of health
checks. Run it from the backend/ folder:

    uvicorn app.main:app --reload
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database.database import init_db
from app.routes import chats, image, websocket

# Images are saved under IMAGE_DIR (e.g. app/static/images); we serve its parent.
STATIC_DIR = os.path.dirname(settings.IMAGE_DIR)

app = FastAPI(title="Christianity AI Assistant", version="1.0.0")

# Wide-open CORS so any frontend can connect during development.
# Lock allow_origins down before putting this on the internet.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Make sure the DB tables and the image folder exist before serving traffic."""
    init_db()
    os.makedirs(settings.IMAGE_DIR, exist_ok=True)


# StaticFiles needs the folder to exist at mount time, so create it now.
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(chats.router)
app.include_router(image.router)
app.include_router(websocket.router)


@app.get("/")
def root():
    """Quick "is it up?" banner."""
    return {"status": "ok", "service": "Christianity AI Assistant"}


@app.get("/health")
def health():
    """Health check for load balancers / uptime monitors."""
    return {"status": "healthy"}
