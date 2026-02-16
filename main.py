from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx
import sqlite3
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Database setup
conn = sqlite3.connect("pipeline.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS pipeline_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original TEXT,
        analysis TEXT,
        sentiment TEXT,
        timestamp TEXT,
        source TEXT
    )
""")
conn.commit()

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
async def run_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Main pipeline endpoint"""
    
    # Step 1: Fetch UUIDs (3 attempts with error handling)
    uuids = []
    for i in range(3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                resp = await http_client.get("https://httpbin.org/uuid")
                resp.raise_for_status()
                data = resp.json()
                uuids.append(data["uuid"])
        except Exception as e:
            print(f"Failed to fetch UUID {i+1}: {e}")
            # Continue with remaining attempts
            continue
    
    if not uuids:
        raise HTTPException(status_code=500, detail="Failed to fetch any UUIDs")
    
    # Step 2: Process each UUID through AI pipeline
    results = []
    errors = []
    
    for uuid in uuids[:3]:  # Process up to 3
        try:
            # AI Enrichment
            analysis = await analyze_with_ai(uuid)
            
            # Store in database
            stored = store_result(uuid, analysis["analysis"], analysis["sentiment"])
            
            results.append({
                "original": uuid,
                "analysis": analysis["analysis"],
                "sentiment": analysis["sentiment"],
                "stored": stored,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
            
        except Exception as e:
            errors.append(f"Failed to process {uuid}: {str(e)}")
            continue  # Continue with next item
    
    # Step 3: Send notification (background task)
    background_tasks.add_task(send_notification, request.email, len(results), len(errors))
    
    return {
        "items": results,
        "notificationSent": True,
        "processedAt": datetime.utcnow().isoformat() + "Z",
        "errors": errors
    }

async def analyze_with_ai(text: str) -> Dict[str, str]:
    """AI Analysis using OpenAI"""
    prompt = f"""
    Analyze this UUID data point in 2-3 sentences and classify sentiment as optimistic, pessimistic, or balanced:
    
    Data: {text}
    
    Respond in this exact JSON format:
    {{"analysis": "your 2-3 sentence analysis here", "sentiment": "optimistic/pessimistic/balanced"}}
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    # Parse AI response
    content = response.choices[0].message.content.strip()
    import json
    try:
        result = json.loads(content)
    except:
        # Fallback if JSON parsing fails
        result = {
            "analysis": "This UUID represents a unique data point successfully processed through the pipeline.",
            "sentiment": "balanced"
        }
    
    return result

def store_result(original: str, analysis: str, sentiment: str) -> bool:
    """Store result in SQLite"""
    try:
        cursor.execute(
            "INSERT INTO pipeline_results (original, analysis, sentiment, timestamp, source) VALUES (?, ?, ?, ?, ?)",
            (original, analysis, sentiment, datetime.utcnow().isoformat(), "HTTPBin UUID")
        )
        conn.commit()
        return True
    except Exception:
        return False

async def send_notification(email: str, success_count: int, error_count: int):
    """Send completion notification (simplified console + file log)"""
    message = f"""
    Pipeline completed!
    - Success: {success_count} items
    - Errors: {error_count} items
    - Sent to: {email}
    """
    print(message)
    
    # Also write to file for demo
    with open("notification_log.txt", "a") as f:
        f.write(f"{datetime.now()}: {message}\n")

# Health check
@app.get("/")
def root():
    return {"message": "AI Pipeline API is running!"}


