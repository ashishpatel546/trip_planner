from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, AsyncGenerator
from datetime import datetime
import uuid
import json
import asyncio
import queue
import os
from pathlib import Path
from dotenv import load_dotenv
from trip_planner.crew import TripPlanner

# Load environment variables from .env file
load_dotenv(override=True)
print(f"DEBUG: OPENAI_API_KEY loaded: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No'}")
print(f"DEBUG: Current CWD: {os.getcwd()}")

app = FastAPI(
    title="Trip Planner API v2",
    description="AI-powered trip planning with real-time SSE updates",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

trip_requests: Dict[str, dict] = {}
progress_queues: Dict[str, queue.Queue] = {}


class TripRequest(BaseModel):
    origin: str
    cities: str
    travel_dates: str
    trip_days: str
    interests: str
    tip_amount: Optional[str] = "1000"
    currency: Optional[str] = Field("USD", description="Preferred currency: USD or INR (default: USD)")
    travelers: Optional[int] = Field(1, description="Number of travelers (default: 1)")


class TripResponse(BaseModel):
    request_id: str
    status: str
    message: str
    created_at: str


def emit_progress(request_id: str, message: str, agent: str, status: str):
    progress_item = {
        "message": message,
        "agent": agent,
        "status": status,
        "timestamp": datetime.now().isoformat()
    }
    
    if "progress_details" not in trip_requests[request_id]:
        trip_requests[request_id]["progress_details"] = []
    trip_requests[request_id]["progress_details"].append(progress_item)
    trip_requests[request_id]["progress"] = message
    trip_requests[request_id]["updated_at"] = datetime.now().isoformat()
    
    if request_id in progress_queues:
        try:
            progress_queues[request_id].put(progress_item)
        except:
            pass


def run_trip_planner(request_id: str, inputs: dict):
    try:
        emit_progress(request_id, "🚀 Initializing Trip Planner", "system", "info")
        
        trip_requests[request_id]["status"] = "processing"
        trip_requests[request_id]["updated_at"] = datetime.now().isoformat()
        
        planner = TripPlanner()
        planner.progress_queue = progress_queues.get(request_id)
        
        # Add task callbacks
        original_emit = planner._emit_progress
        def enhanced_emit(message, agent="", status="info"):
            emit_progress(request_id, message, agent, status)
            original_emit(message, agent, status)
        planner._emit_progress = enhanced_emit
        
        crew = planner.crew()
        
        emit_progress(request_id, "🎯 Starting city selection and flight search", "city_selection_expert", "working")
        
        result = crew.kickoff(inputs=inputs)
        
        # Emit task-specific progress based on execution
        emit_progress(request_id, "📍 Gathering local tour details and attractions", "local_expert", "working")
        emit_progress(request_id, "🗺️ Creating final itinerary plan", "travel_concierge", "working")
        emit_progress(request_id, "✅ Trip planning completed!", "system", "success")
        
        trip_requests[request_id]["status"] = "completed"
        trip_requests[request_id]["result"] = {
            "raw_output": result.raw,
            "final_report": result.raw
        }
        trip_requests[request_id]["updated_at"] = datetime.now().isoformat()
        
    except Exception as e:
        emit_progress(request_id, f"❌ Error: {str(e)}", "system", "error")
        trip_requests[request_id]["status"] = "failed"
        trip_requests[request_id]["progress"] = f"Error: {str(e)}"
        trip_requests[request_id]["updated_at"] = datetime.now().isoformat()


@app.get("/")
def read_root():
    return {
        "service": "Trip Planner API v2",
        "status": "running",
        "version": "2.0.0",
        "features": ["SSE", "Real-time progress", "Amadeus flights"]
    }


@app.post("/api/v1/trips/plan", response_model=TripResponse)
async def create_trip_plan(request: TripRequest, background_tasks: BackgroundTasks):
    request_id = str(uuid.uuid4())
    progress_queues[request_id] = queue.Queue(maxsize=100)
    
    trip_requests[request_id] = {
        "request_id": request_id,
        "status": "queued",
        "progress": "Request received",
        "progress_details": [],
        "inputs": request.dict(),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    background_tasks.add_task(run_trip_planner, request_id, request.dict())
    
    return TripResponse(
        request_id=request_id,
        status="queued",
        message="Trip planning started. Use /stream/{request_id} for real-time updates.",
        created_at=trip_requests[request_id]["created_at"]
    )


@app.get("/api/v1/trips/{request_id}/status")
async def get_trip_status(request_id: str):
    if request_id not in trip_requests:
        raise HTTPException(status_code=404, detail="Trip request not found")
    
    trip_data = trip_requests[request_id]
    
    return {
        "request_id": request_id,
        "status": trip_data["status"],
        "progress": trip_data["progress"],
        "progress_details": trip_data.get("progress_details", []),
        "result": trip_data.get("result"),
        "created_at": trip_data["created_at"],
        "updated_at": trip_data["updated_at"]
    }


@app.get("/api/v1/trips/{request_id}/stream")
async def stream_progress(request_id: str):
    if request_id not in trip_requests:
        raise HTTPException(status_code=404, detail="Trip request not found")
    
    if request_id not in progress_queues:
        raise HTTPException(status_code=404, detail="Progress stream not available")
    
    async def event_generator() -> AsyncGenerator[str, None]:
        progress_queue = progress_queues[request_id]
        
        yield f"data: {json.dumps({'message': 'Connected', 'status': 'connected'})}\n\n"
        
        for item in trip_requests[request_id].get("progress_details", []):
            yield f"data: {json.dumps(item)}\n\n"
            await asyncio.sleep(0.05)
        
        while True:
            try:
                if trip_requests[request_id]["status"] in ["completed", "failed"]:
                    yield f"data: {json.dumps({'message': 'Stream ended', 'status': trip_requests[request_id]['status']})}\n\n"
                    break
                
                try:
                    item = progress_queue.get(timeout=1)
                    yield f"data: {json.dumps(item)}\n\n"
                except queue.Empty:
                    yield f": keepalive\n\n"
                    await asyncio.sleep(0.5)
                    
            except asyncio.CancelledError:
                break
            except Exception:
                break
        
        if request_id in progress_queues:
            del progress_queues[request_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/v1/trips/{request_id}/result")
async def get_trip_result(request_id: str):
    if request_id not in trip_requests:
        raise HTTPException(status_code=404, detail="Trip request not found")
    
    trip_data = trip_requests[request_id]
    
    if trip_data["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Trip is {trip_data['status']}: {trip_data['progress']}"
        )
    
    return {
        "request_id": request_id,
        "status": "completed",
        "result": trip_data["result"],
        "progress_details": trip_data.get("progress_details", []),
        "created_at": trip_data["created_at"],
        "completed_at": trip_data["updated_at"]
    }


@app.get("/api/v1/trips")
async def list_trips():
    return {
        "trips": [
            {
                "request_id": req_id,
                "status": data["status"],
                "progress": data["progress"],
                "created_at": data["created_at"]
            }
            for req_id, data in trip_requests.items()
        ],
        "total": len(trip_requests)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
