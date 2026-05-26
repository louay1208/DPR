"""WebSocket endpoint for real-time log streaming."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.logger import LogService

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/logs")
async def log_stream(ws: WebSocket) -> None:
    """Stream log entries to connected clients in real time."""
    logger = LogService.get()
    await logger.connect(ws)

    try:
        while True:
            # Keep connection alive; client can also send commands
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.disconnect(ws)
