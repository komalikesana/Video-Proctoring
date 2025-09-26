from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import cv2
import numpy as np
from logger_utils import add_candidate, log_event, generate_report, end_candidate_session
from detection import analyze_frame as detect_frame, end_candidate, SCORE_DEDUCTIONS
import sqlite3
import json


BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
os.makedirs(LOG_DIR, exist_ok=True)

DB_PATH = os.path.join(LOG_DIR, "events.db")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Serve frontend ----------------
@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# ---------------- Get candidates ----------------
@app.get("/candidates")
def get_candidates():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT candidate_id, candidate_name, integrity_score, start_time, end_time FROM candidates"
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "name": row[1],
            "integrity_score": row[2],
            "start_time": row[3],
            "end_time": row[4]
        }
        for row in rows
    ]

# ---------------- Add candidate ----------------
@app.post("/add-candidate")
def api_add_candidate(name: str = Form(...)):
    candidate_id = add_candidate(name)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT integrity_score, start_time, end_time FROM candidates WHERE candidate_id=?",
        (candidate_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return {
        "id": candidate_id,
        "name": name,
        "integrity_score": row[0],
        "start_time": row[1],
        "end_time": row[2]
    }

@app.post("/log-events")
def api_log_events(candidate_id: int = Form(...), events: str = Form(...)):
    """
    Receives events from frontend (like cell phone/book/laptop detection)
    and logs them into the database using logger_utils.log_event
    """
    try:
        events_list = json.loads(events)  # frontend should send JSON array as string
        for event in events_list:
            log_event(candidate_id, event, score_change=SCORE_DEDUCTIONS.get(event, 0))
        return {"status": "success", "events": events_list}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------- Analyze frame ----------------
@app.post("/analyze-frame")
async def analyze_frame_api(file: UploadFile = File(...), candidate_id: int = Form(...)):
    contents = await file.read()
    npimg = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    # Use detection.py exactly
    results = detect_frame(frame, candidate_id)

    # Update integrity score in DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE candidates SET integrity_score = ? WHERE candidate_id=?",
        (results["score"], candidate_id)
    )
    conn.commit()
    conn.close()

    return results

# ---------------- End session ----------------
@app.post("/end-session")
def api_end_session(candidate_id: int = Form(...)):
    end_candidate(candidate_id)
    end_candidate_session(candidate_id)
    return {"status": "success", "candidate_id": candidate_id}

# ---------------- Generate CSV report ----------------
@app.get("/generate-report")
def api_generate_report(candidate_id: int):
    report_path = generate_report(candidate_id)
    return {"report_path": report_path}

# ---------------- Run server ----------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
