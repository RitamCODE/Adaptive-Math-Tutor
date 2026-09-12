const API_BASE = "http://localhost:8000";

async function handle(response) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `request failed with status ${response.status}`);
  }
  return response.json();
}

export function startSession(studentId) {
  return fetch(`${API_BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ student_id: studentId }),
  }).then(handle);
}

export function getSession(sessionId) {
  return fetch(`${API_BASE}/sessions/${sessionId}`).then(handle);
}

export function submitAnswer(sessionId, answer, timeTakenSec) {
  return fetch(`${API_BASE}/sessions/${sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer, time_taken_sec: timeTakenSec }),
  }).then(handle);
}

export function getNarrative(sessionId) {
  return fetch(`${API_BASE}/sessions/${sessionId}/narrative`).then(handle);
}
