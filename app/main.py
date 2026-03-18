from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from beanie import init_beanie
import os
from dotenv import load_dotenv
from typing import Any, Dict, cast
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import logging
import certifi
from datetime import datetime, timezone
import time

from .routers import admin, chat, project
from .models.admin import AdminUser, ContactMessage
from .models.chat import ChatSession
from .models.project import Project
from .routers.admin import seed_default_admin
from .services.email import send_lead_notification

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.started_at = time.monotonic()
    app.state.started_at_utc = datetime.now(timezone.utc)

    client = AsyncIOMotorClient(
        os.getenv('MONGO_URL', 'mongodb://localhost:27017'),
        tlsCAFile=certifi.where()
        )
    raw_db = client[os.getenv('DB_NAME', 'portfolio_db')]
    database = cast(AsyncIOMotorDatabase, raw_db)
    await init_beanie(
        database=database,
        document_models=[ChatSession, AdminUser, ContactMessage, Project]
    )   # pyright: ignore[reportArgumentType]
    await seed_default_admin()
    app.state.mongo_client = client
    app.state.mongo_database = database

    logging.info('Connected to the database')
    yield
    client.close()
    logging.info('Disconnected from the database')  


app = FastAPI(
    title="Portfolio Chat API",
    description="AI-powered chat with human handoff capability",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [
    '*',
    r'^https?://.*\.vercel\.app$',
    'http://localhost:3000',
]

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"^https?://.*\.vercel\.app$",
)

app.include_router(chat.router,
                   tags=["Chat"])
app.include_router(admin.router, tags=["Admin"])
app.include_router(project.router, tags=["Projects"])

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uptime_seconds(app: FastAPI) -> float:
    started_at = getattr(app.state, "started_at", None)
    if started_at is None:
        return 0.0
    return round(time.monotonic() - started_at, 3)


async def _database_health(app: FastAPI) -> Dict[str, Any]:
    client = getattr(app.state, "mongo_client", None)
    if client is None:
        return {
            "status": "fail",
            "details": "Mongo client not initialized"
        }

    try:
        start = time.monotonic()
        await client.admin.command("ping")
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            "status": "pass",
            "latency_ms": latency_ms
        }
    except Exception as exc:
        return {
            "status": "fail",
            "details": str(exc)
        }


def _config_health() -> Dict[str, Any]:
    required_envs = [
        "MONGO_URL",
        "DB_NAME",
        "GROQ_API_KEY",
        "ADMIN_AUTH_TOKEN"
    ]
    missing = [env_key for env_key in required_envs if not os.getenv(env_key)]
    if missing:
        return {
            "status": "warn",
            "missing": missing
        }
    return {
        "status": "pass"
    }


@app.get('/', tags=["System"])
async def root():
    return {
        "service": app.title,
        "version": app.version,
        "status": "ok",
        "timestamp": _utc_now_iso(),
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get('/health/live', tags=["Health Check"])
async def health_liveness():
    return {
        "status": "alive",
        "timestamp": _utc_now_iso(),
        "uptime_seconds": _uptime_seconds(app)
    }


@app.get('/health/ready', tags=["Health Check"])
async def health_readiness():
    db_check = await _database_health(app)
    is_ready = db_check.get("status") == "pass"

    payload = {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": _utc_now_iso(),
        "checks": {
            "database": db_check
        }
    }

    if not is_ready:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get('/health', tags=["Health Check"])
async def health_check():
    db_check = await _database_health(app)
    config_check = _config_health()

    checks = {
        "application": {
            "status": "pass"
        },
        "database": db_check,
        "configuration": config_check
    }

    db_ok = db_check.get("status") == "pass"
    config_ok = config_check.get("status") in {"pass", "warn"}

    overall_status = "healthy" if db_ok and config_ok else "unhealthy"
    payload = {
        "status": overall_status,
        "service": app.title,
        "version": app.version,
        "timestamp": _utc_now_iso(),
        "uptime_seconds": _uptime_seconds(app),
        "checks": checks
    }

    if overall_status != "healthy":
        return JSONResponse(status_code=503, content=payload)
    return payload


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)))