from fastapi import FastAPI, HTTPException
from profanity_check import predict_prob
from sqlmodel import Session, SQLModel, create_engine, select
from models import BlockedUsername
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True
)

# Create tables
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

class Username(BaseModel):
    text: str

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.post("/check-username")
async def check_username(username: Username):
    try:
        with Session(engine) as session:
            statement = select(BlockedUsername).where(BlockedUsername.username == username.text.lower())
            result = session.exec(statement).first()
            
            if result:
                return {
                    "text": username.text,
                    "is_inappropriate": True,
                    "confidence": 1.0,
                    "reason": "blocked_list"
                }
        
        score = float(predict_prob([username.text])[0])
        return {
            "text": username.text,
            "is_inappropriate": bool(score > 0.7),
            "confidence": score,
            "reason": "profanity_check" if score > 0.7 else None
        }
    except Exception as e:
        logger.error(f"Error checking username: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/block-username")
async def block_username(username: Username):
    try:
        with Session(engine) as session:
            blocked = BlockedUsername(username=username.text.lower())
            session.add(blocked)
            session.commit()
        return {"message": f"Username '{username.text}' has been blocked"}
    except Exception as e:
        logger.error(f"Error blocking username: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/blocked-usernames")
async def get_blocked_usernames():
    try:
        with Session(engine) as session:
            statement = select(BlockedUsername)
            results = session.exec(statement).all()
            return {"blocked_usernames": [result.username for result in results]}
    except Exception as e:
        logger.error(f"Error getting blocked usernames: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))