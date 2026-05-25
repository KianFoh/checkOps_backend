import asyncio
import contextlib
import logging
from pathlib import Path
import sys

from fastapi import FastAPI

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routers import auth
from app.routers import example
from app.routers import notification
from app.routers import realtime
from app.routers import task
from app.routers import user
from app.database import SessionLocal


app = FastAPI()
logger = logging.getLogger(__name__)
recurrence_scheduler_task: asyncio.Task | None = None
RECURRENCE_SCHEDULER_INTERVAL_SECONDS = 30


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.include_router(example.router)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(task.router)
app.include_router(notification.router)
app.include_router(realtime.router)


async def recurrence_scheduler_loop() -> None:
    while True:
        db = SessionLocal()
        try:
            task.generate_due_task_entries(db)
        except Exception:
            db.rollback()
            logger.exception("Failed to generate due recurring task entries.")
        finally:
            db.close()

        await asyncio.sleep(RECURRENCE_SCHEDULER_INTERVAL_SECONDS)


@app.on_event("startup")
async def start_recurrence_scheduler() -> None:
    global recurrence_scheduler_task
    recurrence_scheduler_task = asyncio.create_task(recurrence_scheduler_loop())


@app.on_event("shutdown")
async def stop_recurrence_scheduler() -> None:
    if recurrence_scheduler_task is None:
        return

    recurrence_scheduler_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await recurrence_scheduler_task


@app.get("/")
def read_root():
    return {"message": "Welcome to the Smart Checklist Management System!"}
