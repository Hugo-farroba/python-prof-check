from fastapi import FastAPI, HTTPException, Depends
from profanity_check import predict_prob
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import numpy as np

from database import SessionLocal, BlockedUsername

# Load environment variables
load_dotenv()

class Username(BaseModel):
    text: str

app = FastAPI()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/check-username")
async def check_username(username: Username, db: Session = Depends(get_db)):
    try:        
        # Check if username is blocked in database
        blocked = db.query(BlockedUsername).filter(BlockedUsername.username == username.text).first()
        
        # Check profanity
        score = float(predict_prob([username.text])[0])
        
        return {
            "text": username.text,
            "is_inappropriate": bool(score > 0.7),
            "is_blocked": blocked is not None,
            "confidence": score,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/block-username")
async def block_username(username: Username, db: Session = Depends(get_db)):
    try:
        blocked = BlockedUsername(username=username.text)
        db.add(blocked)
        db.commit()
        return {"message": f"Username '{username.text}' has been blocked"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/blocked-usernames")
async def get_blocked_usernames(db: Session = Depends(get_db)):
    try:
        blocked_usernames = db.query(BlockedUsername).all()
        return {"blocked_usernames": [u.username for u in blocked_usernames]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))