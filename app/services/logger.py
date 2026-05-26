"""Centralized logging service with WebSocket broadcast."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import WebSocket

from app.config import LOG_DIR


class LogService:
    """Manages application logs and broadcasts them to WebSocket clients."""

    _instance: LogService | None = None

    def __init__(self) -> None:
        self._clients: list[WebSocket] = []
        self._history: list[dict[str, Any]] = []
        self._max_history = 500
        self._log_file = LOG_DIR / f"dpr_{datetime.now():%Y%m%d}.log"

    @classmethod
    def get(cls) -> LogService:
        """Return the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Client management ──────────────────────────────────────────────

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)
        # Send recent history on connect
        for entry in self._history[-50:]:
            await ws.send_json(entry)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)

    # ── Logging ────────────────────────────────────────────────────────

    async def log(
        self,
        message: str,
        level: str = "info",
        source: str = "system",
    ) -> dict[str, Any]:
        """Log a message and broadcast to all connected clients."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "source": source,
            "message": message,
        }

        # Store in history
        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Persist to file
        self._write_to_file(entry)

        # Broadcast to WebSocket clients
        await self._broadcast(entry)

        return entry

    async def info(self, message: str, source: str = "system") -> None:
        await self.log(message, "info", source)

    async def success(self, message: str, source: str = "system") -> None:
        await self.log(message, "success", source)

    async def warning(self, message: str, source: str = "system") -> None:
        await self.log(message, "warning", source)

    async def error(self, message: str, source: str = "system") -> None:
        await self.log(message, "error", source)

    # ── History ────────────────────────────────────────────────────────

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._history[-limit:]

    def clear_history(self) -> None:
        self._history.clear()

    # ── Internals ──────────────────────────────────────────────────────

    async def _broadcast(self, entry: dict[str, Any]) -> None:
        """Send a log entry to all connected WebSocket clients."""
        dead: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_json(entry)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def _write_to_file(self, entry: dict[str, Any]) -> None:
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # Non-critical — don't crash the app for a log write failure
