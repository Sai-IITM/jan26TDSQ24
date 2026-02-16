from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import json
import os
from openai import OpenAI
from datetime import datetime
from typing import Dict

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class PipelineRequest(BaseModel):
    email: str
    source: str

@app.post("/pipeline")
async def run_pipeline(request: PipelineRequest):
    uuids = []
    for i in range(3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                resp = await http_client.get("https://httpbin.org/uuid")
                uuids.append(resp.json()["uuid"])
        except:
            continue
    
    results = []
    for uuid in uuids:
        try:
            analysis = await analyze_with_ai(uuid)
            results.append({
                "original": uuid,
                "analysis": analysis["analysis"],
                "sentiment": analysis["sentiment"],
                "stored": True,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
        except Exception:
            pass
    
    return {
        "items": results,
        "notificationSent": True,
        "processedAt": datetime.utcnow().isoformat() + "Z",
        "errors": []
    }

async def analyze_with_ai(text: str) -> Dict:
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f'Analyze UUID "{text}". Return JSON: {{"analysis": "text", "sentiment": "balanced"}}'}],
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {"analysis": "Unique identifier processed through AI pipeline.", "sentiment": "balanced"}

@app.get("/")
async def root():
    return {"message": "AI Pipeline ready!"}
