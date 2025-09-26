const video = document.getElementById('video');
const statusText = document.getElementById('status');
const candidateSelect = document.getElementById('candidateSelect');
const newCandidateInput = document.getElementById('newCandidate');
const addCandidateBtn = document.getElementById('addCandidateBtn');
const endSessionBtn = document.getElementById('endSessionBtn');
const integrityScoreElem = document.getElementById('integrityScore');
const generateReportBtn = document.getElementById('generateReportBtn');

let candidatesData = [];
let activeCandidateId = null;
let stream = null;
let objectModel = null;

// Overlay canvas
const overlayCanvas = document.createElement('canvas');
const overlayCtx = overlayCanvas.getContext('2d');

// Event cooldown
const EVENT_COOLDOWN = 5000; // 5 seconds in ms
const lastEventTime = {}; // candidateId -> { eventName: timestamp }

// ---------------- Load candidates ----------------
async function loadCandidates() {
  try {
    const res = await fetch("http://127.0.0.1:8000/candidates");
    const data = await res.json();
    candidatesData = Array.isArray(data) ? data : data.candidates ?? [];

    candidateSelect.innerHTML = '<option value="">-- Select --</option>';
    candidatesData.forEach(c => {
      const option = document.createElement("option");
      option.value = String(c.id);
      option.textContent = `${c.name} (ID: ${c.id})`;
      candidateSelect.appendChild(option);
    });

    statusText.textContent = candidatesData.length
      ? "Candidates loaded. Select one to start."
      : "No candidates found.";
  } catch (err) {
    console.error("Error loading candidates:", err);
    statusText.textContent = "Error loading candidates: " + err;
  }
}

// ---------------- Show candidate info ----------------
function showCandidateInfo(candidateId) {
  const c = candidatesData.find(c => String(c.id) === String(candidateId));
  if (!c) return;
  integrityScoreElem.textContent = c.integrity_score ?? "-";
}

// ---------------- Camera ----------------
async function startCamera() {
  try {
    if (!stream) {
      stream = await navigator.mediaDevices.getUserMedia({ video: true });
      video.srcObject = stream;
      await video.play();
    }

    overlayCanvas.width = video.videoWidth;
    overlayCanvas.height = video.videoHeight;
    overlayCanvas.style.position = 'absolute';
    overlayCanvas.style.left = video.offsetLeft + 'px';
    overlayCanvas.style.top = video.offsetTop + 'px';
    document.querySelector('.video-container').appendChild(overlayCanvas);

    statusText.textContent = "Loading detection models...";

    // Load face-api.js Tiny Face Detector
    await faceapi.nets.tinyFaceDetector.loadFromUri('https://justadudewhohacks.github.io/face-api.js/models');

    // Load COCO-SSD object detection
    objectModel = await cocoSsd.load();

    statusText.textContent = "✅ Camera ready. Monitoring started...";
    detectFrame();
  } catch (err) {
    console.error("Camera error:", err);
    statusText.textContent = "❌ Could not access webcam or load models: " + err;
  }
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach(track => track.stop());
    stream = null;
  }
  if (overlayCanvas.parentNode) overlayCanvas.parentNode.removeChild(overlayCanvas);
  video.style.display = "none";
}

// ---------------- Generate Report ----------------
generateReportBtn.addEventListener("click", async () => {
  if (!activeCandidateId) {
    statusText.textContent = "⚠️ Please select a candidate first to generate report.";
    return;
  }

  try {
    const res = await fetch(`http://127.0.0.1:8000/generate-report?candidate_id=${activeCandidateId}`);
    const data = await res.json();
    if (data.report_path) {
      const link = document.createElement('a');
      link.href = data.report_path;
      link.download = data.report_path.split('/').pop();
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      statusText.textContent = "✅ Report generated and downloaded.";
    } else {
      statusText.textContent = "⚠️ Could not generate report.";
    }
  } catch (err) {
    console.error("Error generating report:", err);
    statusText.textContent = "Error generating report: " + err;
  }
});

// ---------------- Detect frame ----------------
async function detectFrame() {
  if (!stream || !activeCandidateId) return;

  overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

  const now = Date.now();
  if (!lastEventTime[activeCandidateId]) lastEventTime[activeCandidateId] = {};

  // --- Object Detection ---
  const predictions = await objectModel.detect(video);
  const detectedObjects = predictions
    .filter(p => ["cell phone", "book", "laptop"].includes(p.class))
    .map(p => p.class);

  detectedObjects.forEach(obj => {
    if (!lastEventTime[activeCandidateId][obj] || now - lastEventTime[activeCandidateId][obj] > EVENT_COOLDOWN) {
      sendEventsToBackend([obj]);
      lastEventTime[activeCandidateId][obj] = now;
    }
  });

  // Draw boxes for all detected objects
  predictions.forEach(p => {
    overlayCtx.strokeStyle = ["cell phone", "book", "laptop"].includes(p.class) ? "red" : "green";
    overlayCtx.lineWidth = 2;
    overlayCtx.strokeRect(p.bbox[0], p.bbox[1], p.bbox[2], p.bbox[3]);
    overlayCtx.font = "18px Arial";
    overlayCtx.fillStyle = overlayCtx.strokeStyle;
    overlayCtx.fillText(p.class, p.bbox[0], p.bbox[1] > 20 ? p.bbox[1] - 5 : 20);
  });

  // --- Face Detection ---
  const detections = await faceapi.detectAllFaces(video, new faceapi.TinyFaceDetectorOptions());
  const faceEvents = [];

  if (detections.length === 0) {
    const event = "no_face_detected";
    if (!lastEventTime[activeCandidateId][event] || now - lastEventTime[activeCandidateId][event] > EVENT_COOLDOWN) {
      faceEvents.push(event);
      lastEventTime[activeCandidateId][event] = now;
    }
  }

  if (detections.length > 1) {
    const event = "multiple_faces_detected";
    if (!lastEventTime[activeCandidateId][event] || now - lastEventTime[activeCandidateId][event] > EVENT_COOLDOWN) {
      faceEvents.push(event);
      lastEventTime[activeCandidateId][event] = now;
    }
  }

  if (detections.length === 1) {
    const box = detections[0].box;
    const faceCenterX = box.x + box.width / 2;
    const frameCenterX = video.videoWidth / 2;
    if (Math.abs(faceCenterX - frameCenterX) > video.videoWidth * 0.25) {
      const event = "candidate_not_looking_at_screen";
      if (!lastEventTime[activeCandidateId][event] || now - lastEventTime[activeCandidateId][event] > EVENT_COOLDOWN) {
        faceEvents.push(event);
        lastEventTime[activeCandidateId][event] = now;
      }
    }
  }

  if (faceEvents.length) sendEventsToBackend(faceEvents);

  // Update status
  const allEvents = [...detectedObjects.filter(obj => detectedObjects.includes(obj)), ...faceEvents];
  statusText.textContent = allEvents.length
    ? "⚠️ Detected: " + allEvents.join(", ")
    : "✅ No violations detected.";

  requestAnimationFrame(detectFrame);
}

// ---------------- Send events to backend ----------------
async function sendEventsToBackend(events) {
  if (!activeCandidateId || !events.length) return;

  const formData = new FormData();
  formData.append("candidate_id", activeCandidateId);
  formData.append("events", JSON.stringify(events));

  try {
    const res = await fetch("http://127.0.0.1:8000/log-events", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (data.score !== undefined) integrityScoreElem.textContent = data.score;
  } catch (err) {
    console.error("Error sending events to backend:", err);
  }
}

// ---------------- Candidate selection ----------------
candidateSelect.addEventListener("change", async () => {
  const selectedId = candidateSelect.value;
  if (!selectedId) {
    stopCamera();
    activeCandidateId = null;
    statusText.textContent = "Select a candidate to start the camera.";
    return;
  }
  activeCandidateId = selectedId;
  showCandidateInfo(activeCandidateId);
  video.style.display = "block";
  await startCamera();
});

// ---------------- Add candidate ----------------
addCandidateBtn.addEventListener("click", async () => {
  const name = newCandidateInput.value.trim();
  if (!name) return;

  const formData = new FormData();
  formData.append("name", name);

  try {
    const res = await fetch("http://127.0.0.1:8000/add-candidate", { method: "POST", body: formData });
    const data = await res.json();

    candidatesData.push(data);
    const option = document.createElement("option");
    option.value = String(data.id);
    option.textContent = `${data.name} (ID: ${data.id})`;
    candidateSelect.appendChild(option);

    newCandidateInput.value = "";
    candidateSelect.value = String(data.id);
    candidateSelect.dispatchEvent(new Event('change'));
  } catch (err) {
    console.error("Error adding candidate:", err);
    statusText.textContent = "Error adding candidate: " + err;
  }
});

// ---------------- End session ----------------
endSessionBtn.addEventListener("click", async () => {
  if (!activeCandidateId) return;
  stopCamera();

  const formData = new FormData();
  formData.append("candidate_id", activeCandidateId);

  await fetch("http://127.0.0.1:8000/end-session", { method: "POST", body: formData });
  activeCandidateId = null;
  candidateSelect.value = "";
  statusText.textContent = "Session ended. Select a candidate to start a new session.";
});

// ---------------- Initialize ----------------
window.addEventListener("DOMContentLoaded", loadCandidates);
