from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from database import init_db


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="Python Learn API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.ai import router as ai_router
app.include_router(ai_router)

from routers.assessment import router as assessment_router
app.include_router(assessment_router)

from routers.users import router as users_router
app.include_router(users_router)

from routers.progress import router as progress_router
app.include_router(progress_router)

from routers.sessions_router import router as sessions_router
app.include_router(sessions_router)

from routers.admin import router as admin_router
app.include_router(admin_router)

from routers.lessons import router as lessons_router
app.include_router(lessons_router)

from pathlib import Path
from fastapi.staticfiles import StaticFiles

_admin_static = Path(__file__).parent / "admin" / "static"
if _admin_static.exists():
    app.mount("/admin-ui", StaticFiles(directory=str(_admin_static), html=True), name="admin-ui")

@app.get("/")
async def root():
    return {"status": "ok", "service": "wixi-app", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}
