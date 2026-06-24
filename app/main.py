import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent.graph import run_agent_stream
from app.observability.logging import log_event, setup_logging

setup_logging()

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

APP_VERSION = "0.1.1"

app = FastAPI(title="Supplier Onboarding Agent", version=APP_VERSION)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(
        default="default",
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_-]+$",
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(
        WEB_DIR / "index.html",
        headers={"Cache-Control": "no-cache"},
    )


@app.post("/chat")
async def chat(request: ChatRequest):
    log_event("chat_request", session_id=request.session_id, message=request.message)

    async def event_stream():
        try:
            for event in run_agent_stream(request.message, session_id=request.session_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # noqa: BLE001
            log_event("chat_error", session_id=request.session_id, error=str(exc))
            yield f"data: {json.dumps({'type': 'error', 'message': 'Agent execution failed. Check server logs.'})}\n\n"
            yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
