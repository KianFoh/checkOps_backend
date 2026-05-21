from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.database import SessionLocal
from app.helpers.realtime import manager
from app.models.session import Session
from app.models.user import User

router = APIRouter(tags=["Realtime"])


def get_user_from_token(token: str | None) -> User | None:
    if not token:
        return None

    db = SessionLocal()
    try:
        db_session = (
            db.query(Session)
            .filter(Session.access_token == token)
            .first()
        )
        if db_session is None:
            return None

        if db_session.access_token_expires_at < datetime.utcnow():
            return None

        user = db.query(User).filter(User.id == db_session.user_id).first()
        if user is None or not user.active:
            return None

        return user
    finally:
        db.close()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    user = get_user_from_token(websocket.query_params.get("token"))
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(user.id, websocket)
    try:
        await websocket.send_json(
            {
                "event": "connected",
                "user_id": user.id,
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user.id, websocket)
