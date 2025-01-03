from fastapi import FastAPI
from profanity_check import predict_prob
from pydantic import BaseModel

class Username(BaseModel):
    text: str

app = FastAPI()

@app.post("/check-username")
async def check_username(username: Username):
    score = predict_prob([username.text])[0]
    
    return {
        "text": username.text,
        "is_inappropriate": score > 0.7,
        "confidence": float(score)
    }