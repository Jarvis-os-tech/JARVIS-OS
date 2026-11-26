/**
 * JARVIS OS · Constellation Desktop Interface & Widget Engine
 * Adapted from Ada Jarvis for the Omarchy OS Wayland Desktop Environment.
 */

import {JarvisOrb} from "/static/orb.js";
import {initWorkspace, workspaceEvent, workspaceUI, workspaceUIState} from "/static/workspace.js";
import {AudioEngine} from "/static/audio/engine.js";
import {initGestures} from "/static/gestures.js";

// Desktop CSS tuning for Omarchy OS Wayland layer
const style = document.createElement("style");
style.textContent = `
  /* Leave space below the JARVIS top session bar (44px) */
  .has-workspace .project-header, .project-header {
    top: 52px !important;
  }
  .connection-info {
    top: 52px !important;
  }
  .project-tabs {
    top: 104px !important;
  }
  /* Constellation panels layout for desktop */
  @media (min-width: 1001px) {
    .has-workspace .panel-plan {
      right: 2% !important;
      left: auto !important;
      width: 34% !important;
      top: 14% !important;
      height: 78% !important;
    }
    .has-workspace .panel-brief {
      left: 2% !important;
      top: 14% !important;
      width: 22% !important;
    }
    .has-workspace .panel-files {
      left: 2% !important;
      top: 34% !important;
      width: 22% !important;
    }
    .has-workspace .panel-ideas {
      left: 2% !important;
      top: 60% !important;
      width: 22% !important;
    }
    .has-workspace .panel-tasks {
      left: 26% !important;
      top: 78% !important;
      width: 38% !important;
    }
  }
  /* Floating vocal controls and settings button */
  .desktop-controls-bar {
    position: fixed;
    bottom: 24px;
    right: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
    z-index: 100;
  }
`;
document.head.appendChild(style);

// Initialize Hand Gestures Tracking
let gestures = null;
try {
  gestures = initGestures();
} catch (e) {
  console.warn("[JARVIS] Gestures initialization deferred:", e);
}

// Visual Orb & State Management (WebGL with Canvas fallback)
window.jarvisDiagnostics?.phase("Starting JARVIS Voice Core…");
const canvasElement = document.querySelector("#orb");
const orb = new JarvisOrb(canvasElement);

const status = document.getElementById("status");
const apiConnection = document.getElementById("apiConnection");
const apiConnectionLabel = document.getElementById("apiConnectionLabel");
const exitButton = document.getElementById("exitButton");
const settingsButton = document.getElementById("settingsButton");
const settingsPanel = document.getElementById("settingsPanel");
const voiceSelect = document.getElementById("voiceSelect");
const voiceStatus = document.getElementById("voiceStatus");
const pauseWhileSpeaking = document.getElementById("pauseWhileSpeaking");
const speakerModeStatus = document.getElementById("speakerModeStatus");
const stopSpeaking = document.getElementById("stopSpeaking");
const instructionsInput = document.getElementById("instructionsInput");
const instructionsSave = document.getElementById("instructionsSave");
const instructionsReset = document.getElementById("instructionsReset");
const instructionsDefault = document.getElementById("instructionsDefault");
const instructionsStatus = document.getElementById("instructionsStatus");
const micSlider = document.getElementById("micVolume");
const micMuteButton = document.getElementById("micMute");
const startupPanel = document.getElementById("startupPanel");

if (startupPanel) startupPanel.hidden = true;

const captions = {
  connecting: "Connecting to JARVIS Core…",
  idle: "Ready — say hello or choose a command.",
  listening: "Listening…",
  thinking: "JARVIS is thinking…",
  speaking: "JARVIS speaking…",
  reconnecting: "Reconnecting to audio stream…",
  error: "System attention required.",
  exiting: "Desktop session suspended."
};

let currentState = "idle";
let config = null;
let preferences = {
  volume: 0.75,
  micGain: 1.0,
  micMuted: false,
  pauseMicrophoneWhileSpeaking: false,
  reducedMotion: false
};
try {
  const saved = JSON.parse(localStorage.getItem("jarvis.preferences") || "{}");
  Object.assign(preferences, saved);
} catch {}

let audioEngine = null;
let audioEnvelope = 0;
let meterFrame = 0;
let lastMeterTime = 0;
let micResumeTimer = 0;
let deferredUI = null;
const uiResults = new Map();

function setState(nextState, description = captions[nextState] || nextState) {
  currentState = nextState;
  document.body.dataset.state = nextState;
  orb.setState(nextState);
  if (status && status.textContent !== description) {
    status.textContent = description;
  }
}

function setApiStatus(connected, label) {
  if (apiConnection) {
    apiConnection.dataset.state = connected ? "connected" : "disconnected";
  }
  if (apiConnectionLabel) {
    apiConnectionLabel.textContent = label || (connected ? "Gemini Live" : "Voice offline");
  }
}

// Settings Panel Controls
function showSettings(show, focus = true) {
  if (!settingsPanel) return;
  settingsPanel.hidden = !show;
  if (settingsButton) {
    settingsButton.setAttribute("aria-expanded", String(show));
    if (focus) (show ? document.getElementById("settingsPanelClose") : settingsButton)?.focus?.();
  }
}

if (settingsButton) {
  settingsButton.onclick = () => showSettings(settingsPanel.hidden);
}
const settingsCloseBtn = document.getElementById("settingsPanelClose");
if (settingsCloseBtn) {
  settingsCloseBtn.onclick = () => showSettings(false);
}

function syncMicControls() {
  const percent = Math.round((Number.isFinite(preferences.micGain) ? Math.max(0, Math.min(2, preferences.micGain)) : 1) * 100);
  if (micSlider) {
    micSlider.value = percent;
    micSlider.setAttribute("aria-valuetext", `${percent}%`);
    const val = document.getElementById("micVolumeValue");
    if (val) val.textContent = `${percent}%`;
  }
  const muted = preferences.micMuted === true;
  if (micMuteButton) {
    micMuteButton.textContent = muted ? "Unmute microphone" : "Mute microphone";
    micMuteButton.setAttribute("aria-pressed", String(muted));
  }
  const notice = document.getElementById("micMutedNotice");
  if (notice) notice.hidden = !muted;
}

function saveAudioPreferences() {
  try {
    localStorage.setItem("jarvis.preferences", JSON.stringify({
      ...preferences,
      micMuted: micResumeTimer ? false : preferences.micMuted
    }));
  } catch {}
}

if (micMuteButton) {
  micMuteButton.onclick = () => {
    clearTimeout(micResumeTimer);
    micResumeTimer = 0;
    preferences.micMuted = preferences.micMuted !== true;
    audioEngine?.mute(preferences.micMuted);
    if (preferences.micMuted) setState("idle");
    syncMicControls();
    saveAudioPreferences();
  };
}

if (micSlider) {
  micSlider.oninput = () => {
    preferences.micGain = Number(micSlider.value) / 100;
    audioEngine?.setMicGain(preferences.micGain);
    syncMicControls();
    saveAudioPreferences();
  };
}

// Web Audio API Speech Capture and Playback Integration
async function initAudioEngine() {
  if (audioEngine) return audioEngine;
  try {
    audioEngine = new AudioEngine(
      // On audio capture callback (frames sent to backend/socket)
      (pcmData) => {
        // Audio capture frames ready
      },
      // On playback event callback
      (event) => {
        if (event.type === "playback_started") {
          setState("speaking");
        } else if (event.type === "playback_drained" || event.type === "playback_stopped") {
          setState("idle");
        }
      }
    );

    await audioEngine.start({
      volume: preferences.volume,
      micGain: preferences.micGain,
      micMuted: preferences.micMuted,
      echoCancellation: true,
      pauseMicrophoneWhileSpeaking: preferences.pauseMicrophoneWhileSpeaking
    });

    console.info("[JARVIS WebAudio] AudioEngine started successfully.");
    return audioEngine;
  } catch (error) {
    console.warn("[JARVIS WebAudio] AudioEngine initialize notice:", error.message || error);
    return null;
  }
}

// User activation recovery for Web Audio
async function resumeAudioOnGesture() {
  if (audioEngine?.context?.state === "suspended") {
    try {
      await audioEngine.context.resume();
      console.info("[JARVIS WebAudio] Context resumed on user interaction.");
    } catch {}
  } else if (!audioEngine) {
    await initAudioEngine();
  }
}
document.querySelector(".stage")?.addEventListener("pointerdown", resumeAudioOnGesture);
window.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") resumeAudioOnGesture();
});

// Audio Metering Loop (reacts to both local WebAudio and Omarchy voice RMS)
let omarchyAudioRms = 0;
function audioMeterLoop(now) {
  meterFrame = requestAnimationFrame(audioMeterLoop);
  if (document.hidden || now - lastMeterTime < 30) return;
  const dt = Math.min((now - (lastMeterTime || now)) / 1000, 0.1);
  lastMeterTime = now;

  let levels = {energy: 0, low: 0, high: 0};
  if (audioEngine?.context && audioEngine.context.state === "running") {
    levels = audioEngine.levels();
  } else {
    levels.energy = omarchyAudioRms;
  }

  // Smooth envelope follower
  const targetEnergy = Math.max(levels.energy, omarchyAudioRms);
  audioEnvelope += (targetEnergy - audioEnvelope) * (1 - Math.exp(-dt / (targetEnergy > audioEnvelope ? 0.035 : 0.23)));
  orb.setAudio({
    ...levels,
    energy: audioEnvelope,
    listening: currentState === "listening" ? Math.max(0.2, audioEnvelope * 3) : 0
  });
}
meterFrame = requestAnimationFrame(audioMeterLoop);

// Sync Settings with Backend API
async function loadConfig() {
  try {
    const res = await fetch("/api/settings");
    if (!res.ok) return;
    config = await res.json();
    if (config?.settings) {
      if (config.settings.volume !== undefined) preferences.volume = config.settings.volume;
      if (config.settings.reduced_motion !== undefined && config.settings.reduced_motion !== null) {
        preferences.reducedMotion = config.settings.reduced_motion;
        orb.reduced = preferences.reducedMotion;
        document.body.dataset.reducedMotion = String(orb.reduced);
      }
    }
    if (config?.voices && voiceSelect) {
      voiceSelect.replaceChildren(
        ...Object.entries(config.voices).map(([name, style]) => new Option(`${name} · ${style}`, name))
      );
      if (config.settings?.voice) voiceSelect.value = config.settings.voice;
      voiceSelect.disabled = false;
    }
    if (instructionsInput && config?.settings?.instructions) {
      instructionsInput.value = config.settings.instructions;
      instructionsInput.disabled = false;
    }
  } catch (err) {
    console.warn("[JARVIS] Could not load /api/settings:", err);
  }
}

if (voiceSelect) {
  voiceSelect.onchange = async () => {
    const newVoice = voiceSelect.value;
    try {
      await fetch("/api/settings/voice", {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({voice: newVoice})
      });
      if (voiceStatus) voiceStatus.textContent = `${newVoice} voice active.`;
    } catch (e) {
      if (voiceStatus) voiceStatus.textContent = "Could not update voice.";
    }
  };
}

// VoiceUIAction Engine: Processes Voice Commands for Settings and UI Panels
export async function voiceUIAction(args) {
  const {action, value} = args;
  const amount = (fallback, min, max) => {
    const n = args.amount ?? fallback;
    if (!Number.isFinite(n) || n < min || n > max) throw Error(`Choose a value between ${min} and ${max}.`);
    return n;
  };

  console.info(`[JARVIS VoiceUIAction] Executing action: "${action}"`, args);

  // 1. UI Panel toggles & Dialogs
  if (["projects", "close", "cancel", "show_response", "save_visible", "confirm", "read_document", "edit_document", "document_section"].includes(action)) {
    if (["close", "cancel"].includes(action)) {
      showSettings(false, false);
      if (action === "cancel") {
        clearTimeout(deferredUI?.timer);
        deferredUI = null;
      }
    } else {
      showSettings(false, false);
    }
    return workspaceUI(action, args);
  }

  // 2. Settings Panel Toggle
  if (action === "settings") {
    await workspaceUI("close");
    showSettings(true, false);
    return {view: "settings"};
  }

  // 3. Tab switching (Overview, Plan, CAD, Parts, Files, Ideas)
  if (action === "tab") {
    const targetTab = value || args.tab;
    const tabBtn = document.querySelector(`.project-tab[data-tab="${targetTab}"]`);
    if (tabBtn) {
      tabBtn.click();
      return {tab: targetTab, success: true};
    }
    throw Error(`Unknown tab: ${targetTab}`);
  }

  // 4. Directional Scrolling
  if (action === "scroll") {
    const dialog = document.getElementById("workspaceDialog");
    const editor = dialog?.open && dialog.querySelector(".code-editor");
    const focused = document.querySelector(".project-panel.is-focused .panel-body");
    const boardScroll = document.body.classList.contains("cad-open")
      ? document.getElementById("cadWorkspace")
      : innerWidth > 1000 && focused && focused.scrollHeight > focused.clientHeight
      ? focused
      : document.getElementById("workspace");
    const target = dialog?.open ? (editor || dialog) : !settingsPanel.hidden ? settingsPanel : boardScroll;
    const direction = args.direction || "down";
    const pages = amount(1, 0.1, 10);
    const top = direction === "top" ? 0
      : direction === "bottom" ? target.scrollHeight
      : target.scrollTop + (direction === "up" ? -1 : direction === "down" ? 1 : 0) * target.clientHeight * 0.8 * pages;
    const left = target.scrollLeft + (direction === "left" ? -1 : direction === "right" ? 1 : 0) * target.clientWidth * 0.8 * pages;
    target.scrollTo({top, left, behavior: "instant"});
    return {scroll_top: target.scrollTop, scroll_left: target.scrollLeft};
  }

  // 5. Microphone Level & Gain
  if (action === "set_microphone_level") {
    const percent = amount(100, 1, 200);
    preferences.micGain = percent / 100;
    audioEngine?.setMicGain(preferences.micGain);
    syncMicControls();
    saveAudioPreferences();
    return {microphone_percent: percent};
  }

  // 6. Timed Microphone Pause (Mute)
  if (action === "pause_microphone") {
    const seconds = amount(15, 1, 300);
    clearTimeout(micResumeTimer);
    preferences.micMuted = true;
    audioEngine?.mute(true);
    syncMicControls();
    micResumeTimer = setTimeout(() => {
      micResumeTimer = 0;
      preferences.micMuted = false;
      audioEngine?.mute(false);
      syncMicControls();
      saveAudioPreferences();
    }, seconds * 1000);
    return {microphone_paused_seconds: seconds, resumes_automatically: true};
  }

  // 7. Volume and Motion Settings
  if (action === "set_volume" || action === "set_motion") {
    if (action === "set_motion" && !["reduced", "full"].includes(value)) {
      throw Error("Choose reduced or full motion.");
    }
    const changes = action === "set_volume"
      ? {volume: amount(75, 0, 100) / 100}
      : {reduced_motion: value === "reduced"};

    if (action === "set_volume") {
      preferences.volume = changes.volume;
      audioEngine?.setVolume(preferences.volume);
    } else {
      preferences.reducedMotion = changes.reduced_motion;
      orb.reduced = preferences.reducedMotion;
      document.body.dataset.reducedMotion = String(orb.reduced);
    }

    try {
      await fetch("/api/settings/audio", {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(changes)
      });
    } catch {}

    saveAudioPreferences();
    return changes;
  }

  // 8. Voice Selection & System Instructions
  if (["set_voice", "set_instructions", "reset_instructions", "save_default_instructions"].includes(action)) {
    if (action === "set_voice") {
      if (config?.voices && !Object.hasOwn(config.voices, value)) {
        throw Error("Choose a supported voice.");
      }
      await fetch("/api/settings/voice", {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({voice: value})
      });
      if (voiceSelect) voiceSelect.value = value;
      return {voice: value, saved: true};
    }
    if (action === "set_instructions") {
      if (typeof value !== "string" || !value.trim()) throw Error("Provide the instructions.");
      await fetch("/api/settings/instructions", {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({instructions: value})
      });
      return {instructions_updated: true};
    }
    if (action === "reset_instructions") {
      await fetch("/api/settings/instructions/reset", {method: "POST"});
      return {instructions_reset: true};
    }
    if (action === "save_default_instructions") {
      await fetch("/api/settings/instructions/default", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({instructions: value || instructionsInput?.value || ""})
      });
      return {default_saved: true};
    }
  }

  // 9. Exit Application / Desktop Session
  if (action === "exit") {
    setState("exiting");
    audioEngine?.close();
    orb.dispose();
    try {
      await fetch("/api/exit", {method: "POST"});
    } catch {}
    return {closing: true};
  }

  throw Error(`Unknown VoiceUIAction action: "${action}"`);
}

// Global UI Request Dispatcher
export async function handleUIRequest(event) {
  if (!event || typeof event.id !== "string") return;
  let response = uiResults.get(event.id);
  if (!response) {
    try {
      const result = event.name === "get_ui_state"
        ? {
            ...workspaceUIState(),
            settings_open: !settingsPanel.hidden,
            settings: {
              voice: config?.settings?.voice || "Zephyr",
              voices: config?.voices || {},
              volume_percent: Math.round(preferences.volume * 100),
              microphone_percent: Math.round(preferences.micGain * 100),
              microphone_muted: preferences.micMuted,
              reduced_motion: orb.reduced
            }
          }
        : event.name === "control_ui"
        ? await voiceUIAction(event.arguments || {})
        : event.name === "control_cad"
        ? await workspaceUI("cad_control", event.arguments || {})
        : ["prepare_print", "control_plate", "control_print"].includes(event.name)
        ? await workspaceUI(event.name, event.arguments || {})
        : null;

      if (!result) throw Error("Unknown screen tool request.");
      response = {type: "ui_result", id: event.id, ok: true, result};
    } catch (error) {
      response = {type: "ui_result", id: event.id, ok: false, error: error.message || "Action failed."};
    }
    uiResults.set(event.id, response);
  }
  return response;
}

// Expose handlers globally for external callers, Wayland IPC, or webview message bridges
window.voiceUIAction = voiceUIAction;
window.handleUIRequest = handleUIRequest;

// Listen to postMessage for embedded window integration
window.addEventListener("message", async (event) => {
  if (event.data?.type === "voice_ui_action") {
    try {
      const res = await voiceUIAction(event.data.arguments || {});
      event.source?.postMessage({type: "voice_ui_result", id: event.data.id, ok: true, result: res}, "*");
    } catch (e) {
      event.source?.postMessage({type: "voice_ui_result", id: event.data.id, ok: false, error: e.message}, "*");
    }
  }
});

// Periodic Synchronization with Omarchy OS Local Voice Subsystem
async function updateVoiceFromOmarchy() {
  try {
    const response = await fetch("/api/voice");
    if (!response.ok) return;
    const voice = await response.json();

    setApiStatus(voice.connected, voice.connected ? "Gemini Live" : "Voice offline");

    if (voice.connected) {
      if (["listening", "thinking", "speaking", "idle"].includes(voice.state)) {
        if (voice.state !== currentState) {
          setState(voice.state);
        }
      }
      omarchyAudioRms = voice.energy || 0;
    } else {
      omarchyAudioRms = 0;
      if (currentState !== "idle" && currentState !== "error") {
        setState("idle");
      }
    }
  } catch {
    setApiStatus(false, "Voice offline");
  }
}

// Mount Workspace and Widgets
initWorkspace((text) => {
  console.info("[JARVIS Workspace] Vocal query / input submitted:", text);
  setState("thinking");
  return true;
});

// Fit orb on layout updates
window.addEventListener("ada:workspace-layout", () => orb.fit());

// Initialize settings, audio, and sync timer
syncMicControls();
loadConfig();
updateVoiceFromOmarchy();
const syncTimer = setInterval(updateVoiceFromOmarchy, 1200);

window.addEventListener("pagehide", () => {
  clearInterval(syncTimer);
  cancelAnimationFrame(meterFrame);
  gestures?.dispose?.();
  audioEngine?.close?.();
  orb.dispose();
}, {once: true});

console.info("[JARVIS Desktop] Initialized with WebGL Core, WebAudio API & VoiceUIAction Engine.");
