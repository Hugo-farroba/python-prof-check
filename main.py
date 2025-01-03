from fastapi import FastAPI, HTTPException, Depends
from profanity_check import predict_prob
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import boto3
import numpy as np

from database import SessionLocal, BlockedUsername

# Load environment variables
load_dotenv()

comprehend = boto3.client('comprehend', region_name='us-east-1')

class Username(BaseModel):
    username: str

app = FastAPI()

async def check_aws_sentiment(text: str):
    try:
        response = comprehend.detect_sentiment(
            Text=text,
            LanguageCode='en'
        )
        is_hate_speech = (
            response['Sentiment'] == 'NEGATIVE' and 
            response['SentimentScore']['Negative'] > 0.8
        )
        return {
            "is_hate_speech": is_hate_speech,
            "confidence": response['SentimentScore']['Negative']
        }
    except Exception as e:
        return {"is_hate_speech": False, "confidence": 0}

def generate_username_variations(username: str) -> list:
    variations = [username]
    if '_' in username:
        variations.append(username.replace('_', ' '))
    return variations

async def check_and_block_username(usernames: list, reason: str, confidence: float, db: Session):
    for username in usernames:
        existing = db.query(BlockedUsername).filter(BlockedUsername.username == username).first()
        if not existing:
            blocked = BlockedUsername(username=username)
            db.add(blocked)
    db.commit()
    return {
        "username": usernames[0],
        "is_inappropriate": True,
        "reason": reason,
        "confidence": confidence
    }

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
        username_variations = generate_username_variations(username.username)
        
        # Step 1: Check if any variation is blocked in database
        for variation in username_variations:
            blocked = db.query(BlockedUsername).filter(
                BlockedUsername.username == variation
            ).first()
            if blocked:
                return {
                    "username": username.username,
                    "is_inappropriate": True,
                    "reason": "database_blocked"
                }

        # Step 2: Check AWS Comprehend for all variations
        for variation in username_variations:
            aws_result = await check_aws_sentiment(variation)
            if aws_result["is_hate_speech"]:
                return await check_and_block_username(
                    username_variations,
                    "aws_comprehend",
                    aws_result["confidence"],
                    db
                )

        # Step 3: Check profanity for all variations
        for variation in username_variations:
            profanity_score = float(predict_prob([variation])[0])
            if profanity_score > 0.7:
                return await check_and_block_username(
                    username_variations,
                    "profanity_check",
                    profanity_score,
                    db
                )
        
        return {
            "username": username.username,
            "is_inappropriate": False,
            "reason": None,
            "confidence": 0
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/block-username")
async def block_username(username: Username, db: Session = Depends(get_db)):
    try:
        blocked = BlockedUsername(username=username.username)
        db.add(blocked)
        db.commit()
        return {"message": f"Username '{username.username}' has been blocked"}
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