"""DPR — Daily Production Report Web Application.

Entry point for the FastAPI application.
Run with:  uv run uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import APP_TITLE, APP_VERSION, STATIC_DIR
from app.core.events import on_shutdown, on_startup
from app.routers import auth, concessions, extract, settings, upload, websocket


# ── Lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()


# ── Application ────────────────────────────────────────────────────────

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    lifespan=lifespan,
)

# CORS (allow all for local development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────

app.include_router(concessions.router)
app.include_router(upload.router)
app.include_router(extract.router)
app.include_router(settings.router)
app.include_router(websocket.router)
app.include_router(auth.router)
app.include_router(auth.users_router)

# ── Static files (frontend) ───────────────────────────────────────────
# Mounted last so API routes take precedence

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
