
from fastapi import FastAPI, Depends
from app.routers import example
from app.database import SessionLocal


app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.include_router(example.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Smart Checklist Management System!"}
