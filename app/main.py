from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from beanie import init_beanie
import os
from dotenv import load_dotenv
from typing import cast
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import logging
import certifi

from .routers import chat
from .models.chat import ChatSession
from .services.email import send_lead_notification

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(
        os.getenv('MONGO_URL', 'mongodb://localhost:27017'),
        tlsCAFile=certifi.where()
        )
    raw_db = client[os.getenv('DB_NAME', 'portfolio_db')]
    database = cast(AsyncIOMotorDatabase, raw_db)
    await init_beanie(database=database, document_models=[ChatSession])   # pyright: ignore[reportArgumentType]
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

@app.get('/health', tags=["Health Check"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get('/test-email', tags=["Testing"])
async def test_email():
    """Test email configuration - sends a test email"""
    test_lead = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "+234-XXX-XXXX"
    }
    
    try:
        result = await send_lead_notification(test_lead, "test_session_email")
        if result:
            return {"status": "success", "message": "Test email sent successfully! Check your inbox."}
        else:
            return {"status": "failed", "message": "Email sending failed. Check backend logs for details."}
    except Exception as e:
        return {"status": "error", "message": f"Error: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)))