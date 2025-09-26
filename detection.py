import cv2
import os
import time
import numpy as np
from logger_utils import log_event  # your custom logging function

# ---------------- Face Detection ----------------
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)
if face_cascade.empty():
    raise ValueError("Failed to load haarcascade_frontalface_default.xml")

# ---------------- Object Templates ----------------
TEMPLATE_DIR = "templates"
OBJECT_TEMPLATES = {}

for fname in os.listdir(TEMPLATE_DIR):
    if fname.lower().endswith((".png", ".jpg", ".jpeg")):
        name = os.path.splitext(fname)[0].lower()  # must match SCORE_DEDUCTIONS
        path = os.path.join(TEMPLATE_DIR, fname)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            OBJECT_TEMPLATES[name] = img

# ---------------- Score Deductions ----------------
SCORE_DEDUCTIONS = {
    "no_face_detected": 10,
    "candidate_not_looking_at_screen": 5,
    "multiple_faces_detected": 15,
    "cell phone": 20,
    "book": 5,
    "laptop": 5,
    "keyboard": 5,
    "mouse": 5,
    "tv": 5,
    "remote": 5
}

MAX_SCORE = 100
EVENT_COOLDOWN = 5  # seconds

# ---------------- Score Calculation ----------------
def calculate_score(events):
    score = MAX_SCORE
    for event in events:
        key = event.strip().lower()
        score -= SCORE_DEDUCTIONS.get(key, 0)
    return max(score, 0)

# ---------------- Focus Detector ----------------
class FocusDetector:
    def __init__(self):
        self.last_face_time = time.time()
        self.last_looked_time = time.time()
        self.active_events = {}  # event_name -> last_logged_time
        self.no_face_threshold = 10
        self.look_away_threshold = 5

    def detect_objects(self, frame_gray):
        """Detect objects using template matching"""
        detected_objects = set()
        for name, template in OBJECT_TEMPLATES.items():
            res = cv2.matchTemplate(frame_gray, template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= 0.6)
            if len(loc[0]) > 0:
                detected_objects.add(name)
        return detected_objects

    def log_event_with_cooldown(self, candidate_id, event_name):
        current_time = time.time()
        last_time = self.active_events.get(event_name, 0)
        if current_time - last_time >= EVENT_COOLDOWN:
            score_change = SCORE_DEDUCTIONS.get(event_name, 0)
            log_event(candidate_id, event_name, score_change)
            self.active_events[event_name] = current_time

    def analyze_frame(self, frame, candidate_id):
        results = {"focused": True, "events": []}
        current_time = time.time()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ---------------- Face Detection ----------------
        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=5, minSize=(40, 40)
        )

        # --- No face detected ---
        if len(faces) == 0 and current_time - self.last_face_time > self.no_face_threshold:
            event = "no_face_detected"
            results["focused"] = False
            results["events"].append(event)
            self.log_event_with_cooldown(candidate_id, event)
        elif len(faces) > 0:
            self.last_face_time = current_time
            self.active_events.pop("no_face_detected", None)

        # --- Multiple faces detected ---
        if len(faces) > 1:
            event = "multiple_faces_detected"
            results["focused"] = False
            results["events"].append(event)
            self.log_event_with_cooldown(candidate_id, event)
        else:
            self.active_events.pop("multiple_faces_detected", None)

        # --- Candidate looking away ---
        if len(faces) == 1:
            x, y, w, h = faces[0]
            face_center_x = x + w / 2
            frame_center_x = frame.shape[1] / 2
            dist_x = abs(face_center_x - frame_center_x)

            if dist_x > frame.shape[1] * 0.25 and current_time - self.last_looked_time > self.look_away_threshold:
                event = "candidate_not_looking_at_screen"
                results["focused"] = False
                results["events"].append(event)
                self.log_event_with_cooldown(candidate_id, event)
            else:
                self.last_looked_time = current_time
                self.active_events.pop("candidate_not_looking_at_screen", None)

        # ---------------- Object Detection ----------------
        detected_objects = self.detect_objects(gray)
        for obj in detected_objects:
            results["events"].append(obj)
            self.log_event_with_cooldown(candidate_id, obj)

        # Remove objects no longer detected
        for tracked_event in list(self.active_events.keys()):
            if tracked_event not in ["no_face_detected", "multiple_faces_detected", "candidate_not_looking_at_screen"] \
               and tracked_event not in detected_objects:
                self.active_events.pop(tracked_event)

        return results

# ---------------- Global Detector Management ----------------
focus_detectors = {}

def analyze_frame(frame, candidate_id):
    if candidate_id not in focus_detectors:
        focus_detectors[candidate_id] = FocusDetector()
    results = focus_detectors[candidate_id].analyze_frame(frame, candidate_id)
    results["score"] = calculate_score(results["events"])
    return results

def end_candidate(candidate_id):
    if candidate_id in focus_detectors:
        del focus_detectors[candidate_id]
