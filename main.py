import os
import sqlite3
import json
import httpx
from datetime import datetime
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="AI Data Pipeline")

# AI Pipe configuration
base_url = "https://aipipe.org/openai/v1"
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=base_url
)

# Database setup
def init_db():
    conn = sqlite3.connect("pipeline.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS results 
                 (id INTEGER PRIMARY KEY, original TEXT, analysis TEXT, 
                  sentiment TEXT, timestamp TEXT, source TEXT)''')
    conn.commit()
    conn.close()

init_db()

class PipelineRequest(BaseModel):
    email: str
    source: str

class PipelineItem(BaseModel):
    original: str
    analysis: str
    sentiment: str
    stored: bool
    timestamp: str

@app.post("/pipeline", response_model=Dict[str, Any])
async def run_pipeline(request: PipelineRequest):
    """Main pipeline endpoint"""
    try:
        # Step 1: Fetch 3 UUIDs from HTTPBin
        uuids = []
        for i in range(3):
            try:
                resp = httpx.get("https://httpbin.org/uuid", timeout=10.0)
                resp.raise_for_status()
                uuid_data = resp.json()
                uuids.append(str(uuid_data.get("uuid", f"uuid-failed-{i}")))
            except Exception as e:
                uuids.append(f"Fetch failed for {i}: {str(e)}")
        
        # Step 2: Process each UUID with AI
        items = []
        errors = []
        
        for i, uuid in enumerate(uuids):
            try:
                # AI Enrichment
                prompt = f"""
                Analyze this UUID string: "{uuid}"
                1. Extract 2-3 key points or observations about it
                2. Classify sentiment as optimistic, pessimistic, or balanced
                Respond in exactly 2 sentences with sentiment at the end.
                """
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100
                )
                
                analysis = response.choices[0].message.content.strip()
                
                # Store in database
                conn = sqlite3.connect("pipeline.db")
                c = conn.cursor()
                c.execute(
                    "INSERT INTO results (original, analysis, sentiment, timestamp, source) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (uuid, analysis, "neutral", datetime.utcnow().isoformat(), request.source)
                )
                conn.commit()
                conn.close()
                
                items.append(PipelineItem(
                    original=uuid,
                    analysis=analysis,
                    sentiment="neutral",  # Extract from analysis if needed
                    stored=True,
                    timestamp=datetime.utcnow().isoformat()
                ))
                
            except Exception as e:
                error_msg = f"Item {i} failed: {str(e)}"
                errors.append(error_msg)
                items.append(PipelineItem(
                    original=uuid,
                    analysis="Analysis failed",
                    sentiment="neutral",
                    stored=False,
                    timestamp=datetime.utcnow().isoformat()
                ))
        
        # Step 3: Send notification (console log for demo)
        notification_msg = f"Pipeline completed for {request.email}. Processed {len(items)} items."
        print(f"🔔 NOTIFICATION SENT TO {request.email}: {notification_msg}")
        
        return {
            "items": [item.dict() for item in items],
            "notificationSent": True,
            "processedAt": datetime.utcnow().isoformat(),
            "errors": errors
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

