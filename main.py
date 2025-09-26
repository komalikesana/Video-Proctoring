from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import cv2
import numpy as np
import sqlite3
import json
from logger_utils import add_candidate, log_event, generate_report, end_candidate_session, init_db
from detection import analyze_frame as detect_frame, end_candidate, SCORE_DEDUCTIONS

# ---------------- Paths ----------------
BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
os.makedirs(LOG_DIR, exist_ok=True)

DB_PATH = os.path.join(LOG_DIR, "events.db")

# ---------------- Initialize Database ----------------
if not os.path.exists(DB_PATH):
    init_db(DB_PATH)  # Make sure init_db uses DB_PATH parameter to create events.db

# ---------------- FastAPI App ----------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Serve Frontend ----------------
# Serve index.html on root
@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# Serve all static files in frontend folder (JS, CSS, images, etc.)
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

# ---------------- API Endpoints ----------------
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
    try:
        events_list = json.loads(events)
        for event in events_list:
            log_event(candidate_id, event, score_change=SCORE_DEDUCTIONS.get(event, 0))
        return {"status": "success", "events": events_list}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/analyze-frame")
async def analyze_frame_api(file: UploadFile = File(...), candidate_id: int = Form(...)):
    contents = await file.read()
    npimg = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    results = detect_frame(frame, candidate_id)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE candidates SET integrity_score = ? WHERE candidate_id=?",
        (results["score"], candidate_id)
    )
    conn.commit()
    conn.close()

    return results

@app.post("/end-session")
def api_end_session(candidate_id: int = Form(...)):
    end_candidate(candidate_id)
    end_candidate_session(candidate_id)
    return {"status": "success", "candidate_id": candidate_id}

@app.get("/generate-report")
def api_generate_report(candidate_id: int):
    report_path = generate_report(candidate_id)
    return {"report_path": report_path}

# ---------------- Run Server ----------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
