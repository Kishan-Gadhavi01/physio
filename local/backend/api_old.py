from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, DESCENDING
from bson import ObjectId
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# --- Database Setup ---
client = MongoClient("mongodb://localhost:27017/")
db = client["Physio"]
sessions_col = db["records"]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for the New, Optimized Data Structure ---
class ProcessedFrameData(BaseModel):
    angle_map: Dict[str, str]
    frame_data: List[List[Any]] # e.g., [frame_id, [angle_values], [keypoints]]
    keypoint_map: Optional[Dict[str, str]] = {}
    skeleton_segments: Optional[Dict[str, Any]] = {}

# This is the model for the POST request body.
# It expects a single key 'data' containing the processed frame data.
class SessionBody(BaseModel):
    data: ProcessedFrameData

# --- API ENDPOINTS ---

@app.post("/api/save_session")
def save_processed_session(session_body: SessionBody):
    """
    Receives a JSON object with a 'data' key and stores it.
    The document in the DB will have the structure: {_id: ..., data: ...}
    """
    document_to_insert = session_body.dict()
    result = sessions_col.insert_one(document_to_insert)
    return {"status": "success", "session_id": str(result.inserted_id)}

@app.get("/api/sessions")
def get_sessions_list():
    """Gets a list of all available session IDs."""
    sessions = sessions_col.find(
        {}, {"_id": 1} # Only fetch the document ID
    ).sort("_id", DESCENDING)
    # The frontend will now only get the ID to display
    return [{"_id": str(s["_id"])} for s in sessions]

@app.get("/api/sessions/{session_id}")
def get_full_session_data(session_id: str):
    """Fetches a single, complete session document by its ID."""
    session = sessions_col.find_one({"_id": ObjectId(session_id)})
    if session:
        session["_id"] = str(session["_id"]) # Convert ObjectId for JSON
        return session
    return {"error": "Session not found"}

