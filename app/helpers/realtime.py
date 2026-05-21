import asyncio
from datetime import datetime

from fastapi import WebSocket


def serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class RealtimeConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[int, list[WebSocket]] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        self.loop = asyncio.get_running_loop()
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        connections = self.active_connections.get(user_id)
        if connections is None:
            return

        if websocket in connections:
            connections.remove(websocket)

        if not connections:
            self.active_connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, event: dict) -> None:
        connections = list(self.active_connections.get(user_id, []))
        for websocket in connections:
            try:
                await websocket.send_json(event)
            except RuntimeError:
                self.disconnect(user_id, websocket)

    def publish_to_user(self, user_id: int, event: dict) -> None:
        if self.loop is None:
            return

        asyncio.run_coroutine_threadsafe(
            self.send_to_user(user_id, event),
            self.loop,
        )


manager = RealtimeConnectionManager()


def publish_task_entry_event(
    user_ids: list[int],
    event_name: str,
    task_id: int,
    task_entry_id: int,
) -> None:
    seen_user_ids: set[int] = set()
    for user_id in user_ids:
        if user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)
        manager.publish_to_user(
            user_id,
            {
                "event": event_name,
                "task_id": task_id,
                "task_entry_id": task_entry_id,
            },
        )


def publish_user_event(
    user_ids: list[int],
    event_name: str,
    target_user_id: int,
) -> None:
    seen_user_ids: set[int] = set()
    for user_id in user_ids:
        if user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)
        manager.publish_to_user(
            user_id,
            {
                "event": event_name,
                "user_id": target_user_id,
            },
        )
