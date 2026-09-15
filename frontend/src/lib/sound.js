// Three short, code-synthesized sound effects (no audio files, no library) —
// a shared AudioContext is created lazily on first use, since browsers only
// allow it to start from inside a user-gesture-adjacent handler. Every
// trigger point in the app fires from a click or a pointer-release, so this
// is satisfied without a separate "enable sound" step. Failures (blocked
// autoplay, unsupported browser) are swallowed rather than thrown.

let ctx = null;

function getContext() {
  if (ctx) return ctx;
  const Ctor = window.AudioContext || window.webkitAudioContext;
  if (!Ctor) return null;
  ctx = new Ctor();
  return ctx;
}

function tone({ freq, startOffset = 0, duration = 0.12, type = "sine", peakGain = 0.15 }) {
  const audioCtx = getContext();
  if (!audioCtx) return;
  if (audioCtx.state === "suspended") audioCtx.resume().catch(() => {});

  const start = audioCtx.currentTime + startOffset;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, start);
  gain.gain.setValueAtTime(0, start);
  gain.gain.linearRampToValueAtTime(peakGain, start + 0.015);
  gain.gain.exponentialRampToValueAtTime(0.001, start + duration);
  osc.connect(gain).connect(audioCtx.destination);
  osc.start(start);
  osc.stop(start + duration + 0.02);
}

export function playCorrectTone() {
  try {
    tone({ freq: 523.25, duration: 0.11, type: "triangle" }); // C5
    tone({ freq: 783.99, startOffset: 0.1, duration: 0.16, type: "triangle" }); // G5
  } catch {
    // sound is decoration, never block on it
  }
}

export function playBundleSnap() {
  try {
    tone({ freq: 220, duration: 0.07, type: "square", peakGain: 0.1 });
  } catch {
    // sound is decoration, never block on it
  }
}

export function playQuestComplete() {
  try {
    const notes = [523.25, 659.25, 783.99, 1046.5]; // C5 E5 G5 C6
    notes.forEach((freq, i) => tone({ freq, startOffset: i * 0.13, duration: 0.2, type: "triangle" }));
  } catch {
    // sound is decoration, never block on it
  }
}
