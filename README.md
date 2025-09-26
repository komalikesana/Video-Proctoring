Video Proctoring System
A web-based candidate video proctoring system using FastAPI, face-api.js, and COCO-SSD object detection.

Features
Real-time face detection and monitoring.
Object detection (e.g., cell phones, books, laptops) during exam.
Candidate session management.
Integrity scoring and event logging.
Report generation in PDF format.
Folder Structure
video-proctoring/ │ ├── backend/ │ ├── main.py │ ├── detection.py │ ├── models/ │ │ └── yolo_model.pt # optional │ ├── logs/ │ │ └── events.db # optional │ ├── utils.py │ │ ├── frontend/ │ ├── index.html │ ├── script.js │ └── style.css └── requirements.txt └── README.md

Installation
# Clone the repository
git clone https://github.com/yourusername/video-proctoring.git
cd video-proctoring/backend

# Create and activate virtual environment
python -m venv venv
# Linux/Mac
source venv/bin/activate
# Windows
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

## Start Backend

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

After this, the backend API endpoints like /candidates, /log-events are available at:

http://127.0.0.1:8000/

## Start Frontend

Open frontend/index.html in a browser (using VS Code Live Server or any static server).

The frontend will connect to the backend APIs to fetch candidates and log events.

## Usage

Select or add a candidate.
Allow webcam access.
The system monitors face and objects in real-time.
Violations are logged, and integrity score updates automatically.
Generate a PDF report after the session.