
from pathlib import Path
import sys

from fastapi import FastAPI, Depends

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routers import auth
from app.routers import example
from app.routers import user
from app.database import SessionLocal


app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.include_router(example.router)
app.include_router(auth.router)
app.include_router(user.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Smart Checklist Management System!"}
