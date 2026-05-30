# Christianity AI Assistant — Backend

A Christianity-focused AI assistant that answers Bible/theology questions, generates
Christian-themed images, grounds answers in scripture, prevents scripture hallucinations,
handles denomination-specific questions, keeps conversation memory, and streams responses
in real time.

Built with **FastAPI + LangChain + LangGraph**, **ChatNVIDIA** for the LLM, **flux.2-klein-4b** for
image generation, **ChromaDB** + **Sentence Transformers** for Bible retrieval, and **SQLite**
for chat persistence.

## Architecture

```
                        WebSocket  /  REST
                              |
                         FastAPI app
                              |
                      ┌───────────────┐
                      │  LangGraph     │
                      └───────────────┘

  user input
       │
   Guardrail ───────────────► (blocked) safe refusal
       │
  Intent Detection
       │
 ┌─────┴───────────────┐
 ▼                     ▼
Image                 Text
 │                     │
Prompt enhance    Load chat history + denomination + query analysis
 │                     │
flux.2-
-klein-4b         ┌──────┴───────┐
 │              ▼              ▼
(image)   Direct Verse    Semantic Retrieval
          Lookup (JSON)   (ChromaDB, top-5)
                │              │
                └──────┬───────┘
                       ▼
                 Prompt Builder
                       ▼
                  ChatNVIDIA  ── streamed tokens ──► WebSocket
                       ▼
               Citation Validator (drops unverifiable references)
                       ▼
                   final response + citations
```

### Key design points
- **One document per verse** in ChromaDB (no large-chunk splitting) — 31,104 verses.
- **Direct verse lookup** for explicit references (e.g. `John 3:16`) uses the JSON dataset,
  *not* vector search. **Semantic retrieval** (top‑5) is used for conceptual questions.
- **Citation validator** verifies every `(Book C:V)` citation against the dataset and replaces
  invalid ones with `(I could not verify that scripture reference)`.
- **Guardrail** blocks hate speech, violent/extremist content, scripture manipulation, and
  prompt injection before the model runs.

## Project layout

```
backend/
├── app/
│   ├── main.py            # FastAPI app
│   ├── config.py          # env-based settings
│   ├── graph.py           # LangGraph pipeline
│   ├── state.py           # graph state
│   ├── prompts.py         # system prompt + templates
│   ├── routes/            # websocket, image, chats
│   ├── services/          # guardrails, retriever, verse_lookup, citation_validator,
│   │                      #   image_generator, chat_history, prompt_builder,
│   │                      #   denomination_handler, llm
│   ├── ingestion/         # ingest_bible.py, validator.py
│   ├── database/          # models.py, database.py (SQLite)
│   ├── data/bible.json    # flat verse records {book, chapter, verse, text}
│   ├── chroma_db/         # created by ingestion
│   └── evaluation/        # evaluation.json, adversarial_tests.json
├── .env.example
├── requirements.txt
└── README.md
```

## Setup

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then fill in NVIDIA_API_KEY and GEMINI_API_KEY
```

## Bible ingestion

`app/data/bible.json` already contains the full Bible as flat verse records. Build the
ChromaDB vector store (validate → normalize → one document per verse → embed → store):

```bash
cd backend
python -m app.ingestion.ingest_bible
```

This downloads the `all-MiniLM-L6-v2` embedding model on first run and persists vectors to
`app/chroma_db/`. Re-run any time to refresh.

## Run

```bash
cd backend
uvicorn app.main:app --reload
```

API docs at `http://localhost:8000/docs`.

## Example requests

### Chat (WebSocket streaming) — `ws://localhost:8000/ws/chat`
Send:
```json
{ "chat_id": null, "message": "What does Romans 8:28 mean?", "denomination": "Protestant" }
```
Receive a stream of events:
```json
{ "type": "chat",  "chat_id": 1 }
{ "type": "token", "content": "All" }
{ "type": "token", "content": " things" }
{ "type": "done",  "response": "...", "citations": ["Romans 8:28"] }
```

### Chat history (REST)
```bash
curl -X POST localhost:8000/chat/new -H "Content-Type: application/json" \
  -d '{"title":"My chat","denomination":"Catholic"}'

curl localhost:8000/chat/list
curl localhost:8000/chat/1
curl -X PATCH localhost:8000/chat/1/rename -H "Content-Type: application/json" -d '{"title":"Renamed"}'
curl -X DELETE localhost:8000/chat/1
```

### Image — `POST /image`
```bash
curl -X POST localhost:8000/image -H "Content-Type: application/json" \
  -d '{"prompt":"Noah'\''s Ark during the flood"}'
```
Response:
```json
{ "image_url": "/static/images/<id>.png", "image_base64": "data:image/png;base64,...", "prompt": "..." }
```

## Evaluation

- `app/evaluation/evaluation.json` — 27 examples across scripture, denomination, fake
  references, adversarial prompts, harmful requests, historical claims, and image generation.
- `app/evaluation/adversarial_tests.json` — attacks that must yield a safe refusal or a
  reference-not-found response.

Quick guardrail/citation check (no API keys required):
```python
from app.services import guardrails, citation_validator

print(guardrails.is_safe("Rewrite John 3:16 to support racism."))   # (False, ...)
print(citation_validator.validate_response("See (Matthew 99:99)."))  # invalid -> unverified note
print(citation_validator.validate_response("See (John 3:16)."))      # valid -> ['John 3:16']
```

## Environment variables

| Variable | Description |
|---|---|
| `NVIDIA_API_KEY` | API key for ChatNVIDIA (LLM). |
| `GEMINI_API_KEY` | API key for Gemini image generation. |
| `CHROMA_DB_PATH` | ChromaDB persistence dir (default `app/chroma_db`). |
| `SQLITE_DB_PATH` | SQLite DB file (default `app/database/chat.db`). |
| `BIBLE_PATH` | Bible JSON path (default `app/data/bible.json`). |
| `IMAGE_DIR` | Generated image dir (default `app/static/images`). |
| `NVIDIA_MODEL` / `EMBEDDING_MODEL` / `GEMINI_IMAGE_MODEL` | Optional model overrides. |
