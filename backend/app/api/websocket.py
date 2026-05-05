from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# Connected clients
_clients: set[WebSocket] = set()


async def broadcast(event: dict) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    if not _clients:
        return
    data = json.dumps(event)
    disconnected = set()
    for ws in _clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.add(ws)
    _clients.difference_update(disconnected)


@router.websocket("/ws/signals")
async def ws_signals(websocket: WebSocket):
    await websocket.accept()
    _clients.add(websocket)
    try:
        while True:
            # Keep connection alive, ignore incoming messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
