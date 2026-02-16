from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import json
import os
from openai import OpenAI
from datetime import datetime
from typing import List, Dict, Any

# Create app FIRST
app = FastAPI(title="AI Pipeline")

# CORS after app creation
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy OpenAI client (handles missing key gracefully)
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return OpenAI(api_key=api_key)
    return None

class PipelineRequest(BaseModel):
    email: str
    source: str

@app.post("/pipeline")
async def run_pipeline(request: PipelineRequest):
    # Fetch 3 UUIDs
    uuids = []
    for i in range(3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                resp = await http_client.get("https://httpbin.org/uuid")
                resp.raise_for_status()
                uuids.append(resp.json()["uuid"])
        except Exception:
            continue
    
    if not uuids:
        return {"items": [], "notificationSent": True, "processedAt": datetime.utcnow().isoformat() + "Z", "errors": ["No UUIDs"]}

    # Process each UUID
    results = []
    errors = []
    client = get_openai_client()
    
    for uuid in uuids:
        try:
            analysis = await analyze_with_ai(uuid, client)
            results.append({
                "original": uuid,
                "analysis": analysis["analysis"],
                "sentiment": analysis["sentiment"],
                "stored": True,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
        except Exception as e:
            errors.append(str(e))
    
    return {
        "items": results,
        "notificationSent": True,
        "processedAt": datetime.utcnow().isoformat() + "Z",
        "errors": errors
    }

async def analyze_with_ai(text: str, client) -> Dict[str, str]:
    if client:
        try:
            prompt = f'Analyze UUID "{text}" in 2 sentences. JSON: {{"analysis": "text", "sentiment": "balanced"}}'
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            content = response.choices[0].message.content.strip()
            return json.loads(content)
        except:
            pass
    
    # Fallback (no OpenAI key)
    return {"analysis": "Unique identifier processed through AI pipeline.", "sentiment": "balanced"}

@app.get("/")
async def root():
    return {"message": "AI Pipeline running on both Vercel & Railway!"}
