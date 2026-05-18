# Smart Checklist Management System

This is a FastAPI-based template for a Smart Checklist Management System.

## Project Structure

- `app/main.py`: FastAPI application entry point
- `app/routers/`: API routers (example included)
- `app/models/`: Pydantic models (example included)

## Setup Instructions

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Run the server:**
   ```bash
   uvicorn app.main:app --reload
   ```
3. **Open in browser:**
   - API docs: http://127.0.0.1:8000/docs

## Customization
- Add your routers in `app/routers/`
- Add your models in `app/models/`
