# JARVIS OS — Sovereign Voice, Desktop Control & Persistent Memory Operating System

A voice-first, persistent memory personal AI operating system foundation for Linux and Omarchy. JARVIS OS integrates ambient acoustic interaction, sub-second local actuation, a multi-tier memory vault, modular external connectors, a native Linux kernel driver, and durable multi-agent orchestration into a normalized, pillar-structured platform.

---

## 🏛️ System Architecture

JARVIS OS organizes system capabilities into normalized top-level pillars:

```
                                  ┌───────────────────────────────┐
                                  │       User Speech / CLI       │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                         ┌─────────────────────────────────────────────────┐
                         │    Human Interaction Engine (HIE) / voice/      │
                         │  • Silero VAD Turn Gating                       │
                         │  • Cactus-Needle Local Command Router (<200ms)  │
                         │  • Instant Situational Spoken Acknowledgements │
                         │  • Gemini Live Duplex Streaming + Auto-VAD     │
                         │  • Fish Audio s2.1-pro Hybrid Speech Synthesis  │
                         │  • Interruption & Playback Cancellation Fence   │
                         └───────┬─────────────────────────────────┬───────┘
                                 │                                 │
                   Local Command │                    Cloud Action │
                                 ▼                                 ▼
┌──────────────────────────────────────────────┐  ┌────────────────────────────────────────────────┐
│         Sovereign Desktop Control            │  │          Agent Orchestration Harness           │
│                  (control/)                  │  │                   (harness/)                   │
│  • Wayland Keyboard & Pointer Actuators      │  │  • Multi-Tier Agent Dispatching (FastAPI REST) │
│  • Hyprland Window & Workspace Management    │  │  • Typed StateGraph & Cyclic Feedback Loops    │
│  • Natural Language Parsing Service          │  │  • Durable Hermes Gateway & State Lineage      │
│  • Action Evidence Collector & Policy Gate   │  │  • Standardized Task Event Lifecycle Contracts │
│  • CUA Semantic Browser Decision Loop        │  │  • Visual Notification Cards & Desktop Notices │
└──────────────────────┬───────────────────────┘  └────────────────────────┬───────────────────────┘
                       │                                                   │
                       └─────────────────────┬─────────────────────────────┘
                                             │
                                             ▼
                      ┌─────────────────────────────────────────────┐
                      │    Sovereign 4-Tier Memory & Knowledge      │
                      │                  (memory/)                  │
                      │  • Zero-RAM SQLite Graph & WAL Ledger       │
                      │  • Bitemporal Staleness & Decay Detectors   │
                      │  • Reciprocal Rank Fusion (BM25 + Cosine)   │
                      │  • Automated Vault Cleaning & Quality Eval  │
                      │  • Bidirectional Obsidian Synchronization   │
                      │  • Model Context Protocol (MCP) Server      │
                      └──────────────────────┬──────────────────────┘
                                             │
                      ┌──────────────────────┼──────────────────────┐
                      │                      │                      │
                      ▼                      ▼                      ▼
┌───────────────────────────┐  ┌───────────────────────────┐  ┌───────────────────────────┐
│ Connectors & External APIs│  │  Kernel Driver & Healing  │  │  Shell, Widgets & UI     │
│       (connectors/)       │  │         (kernel/)         │  │     (shell/ & widgets/)   │
│ • Composio Platform Tools │  │ • /dev/jarvis ioctl & Sys │  │ • Quickshell Wayland HUD  │
│ • Agent Reach Search/Read │  │ • AutoHealer Hardware Fix │  │ • Generative View Schema  │
│ • API-Anything REST/GQL   │  │ • Systemd Unit Recovery   │  │ • 3D Micro-Drone Overlays │
└───────────────────────────┘  └───────────────────────────┘  └───────────────────────────┘
```

---

## 🚀 Key Subsystems

### 1. Human Interaction Engine & Voice Core (`voice/`)
* **Ambient Acoustic Ear**: Continuous PipeWire audio capture (16 kHz PCM, 20 ms frames) with local Silero VAD turn gating.
* **Cactus-Needle Local Command Router**: Embedded high-speed speech recognizer executing offline desktop commands (volume, brightness, app launching, window workspaces, mute, standby) without sending audio to the cloud.
* **Situational Conversational Acknowledgements**: Pre-rendered, affirmative spoken acknowledgements (`On it`, `Looking into that`) matched dynamically to task context (agent tasks, browser searches, file operations, system actions) to eliminate cloud latency without annoying empty vocal fillers ("Ah", "Haa").
* **Duplex Cloud Streaming**: Resilient Gemini Live WebSocket session with Auto-VAD activity detection, automatic reconnection backoff, wake confirmation, and session resumption.
* **Fish Audio Hybrid Synthesis (`voice/fish_speaker.py`)**: Dual-engine routing utilizing Gemini Live for conversational turns paired with Fish Audio (`s2.1-pro`) for high-fidelity announcements, rich narrative reading, and emotional sound effects (`laugh`, `cry`, `sad`, `sigh`).
* **Playback Fencing & Interruption**: Generation-tracked audio buffer instantly halts and flushes speaker queues whenever speech is detected.

### 2. Sovereign Desktop Actuation & Control (`control/`)
* **Wayland Actuators**: Emulated input receipts via `wlr-virtual` / `uinput` for reliable Wayland keyboard typing, modifier chords, and pointer navigation.
* **Hyprland Window Management**: Programmatic workspace switching, window focus, tiling geometry, minimization, and process lifecycle management.
* **Natural Language Parsing Worker**: Dedicated local parsing service translating natural speech phrases into structured desktop actuator commands.
* **Safety & Execution Policy**: Gated execution boundary with denied shell patterns, confirmation words for irreversible actions, and dry-run preview capabilities.
* **Action Evidence Collector**: Structured telemetry recording timestamps, action parameters, verification receipts, and failure outcomes.
* **Semantic Browser Decision Loop (`skills/browser_decision.py`)**: High-speed (~200ms) Gemini Decision 1 browser loop over semantic CUA bindings, bounded with hard safety cutoffs at authentication, CAPTCHA, and payment gates.

### 3. Sovereign 4-Tier Memory Vault (`memory/`)
* **SQLite WAL Ledger & Graph Engine**: ACID-compliant knowledge base with serverless SQLite WAL, FTS5 BM25 search, and recursive CTE graph traversal.
* **Bitemporal Cognitive Modeling (`memory/staleness_detector.py`)**: Tracks memories across Valid Time (real-world applicability) and Transaction Time (recording time) with 4 deterministic zero-model detectors (`TtlDetector`, `KeyCollisionDetector`, `OsRealityDetector`, `TemporalDecayDetector`).
* **Hybrid RRF Retrieval**: Reciprocal Rank Fusion blending full-text FTS5 (BM25) with dense vector embeddings (`text-embedding-004` or Ollama).
* **Taxonomy & Categorization**: Structured schema classifying knowledge across preferences, workflow habits, technical context, entities, and temporal notes.
* **Obsidian Vault Sync**: Continuous bidirectional sync with Obsidian markdown vaults (`JARVIS-OMA Memory/`).
* **MCP Interface**: Exposes memory tools via standard Model Context Protocol (stdio) for agent fleet consumption.

### 4. Linux Kernel Driver & Autonomous Self-Healing (`kernel/`)
* **`/dev/jarvis` Kernel Interface (`kernel/jarvis_dev.py`)**: Native stdlib interface to the `linux-jarvisos` character device and sysfs subsystem (`/sys/class/misc/jarvis`) for hardware-level status, system monitoring (`JarvisSysmon`), and provider state.
* **Zero-Model-Call Hardware Repair (`kernel/self_healer.py`)**: Background reflex engine monitoring audio streams and automatically unmuting inputs, restoring volume, or reloading PipeWire in <100ms without cloud latency.
* **Systemd User Unit Auto-Recovery**: Detects failed systemd user units, issues `systemctl --user reset-failed`, clears stale socket/PID locks, and performs bounded restarts.
* **Proactive Resource Pruning**: Intercepts disk pressure and high memory watermarks to selectively prune temporary audio cache buffers.

### 5. Multi-Agent Orchestration & StateGraph (`harness/`)
* **Typed StateGraph (`harness/state_graph.py`)**: Stateful cyclic graphs with supervisor routing, checkpointing, and critique feedback loops instead of rigid linear DAGs.
* **Hermes Gateway Worker**: Durable gateway managing background subagent execution with heartbeat monitoring and state persistence.
* **Hermes API Server**: Dedicated FastAPI REST interface exposing agent delegation endpoints.
* **Task Event Lifecycle**: Standardized UI event contracts dispatching start, progress, milestone, receipt, and completion notifications.
* **Desktop Presentation Cards**: Rich Quickshell notification widgets rendering agent progress cards on the desktop.

### 6. Quickshell Sci-Fi Desktop Shell (`shell/`, `bin/de`)
* **Native Wayland Desktop Environment**: Custom Quickshell desktop environment tailored for Hyprland and Omarchy.
* **Arc Reactor Core & Telemetry**: Dynamic CPU, GPU, memory, and network telemetry with ambient acoustic waveform visualization.
* **Application Stage & Command Palette**: Desktop entry staging, virtual workspace vaults, and spotlight-style window/app search.
* **Execution Airlock**: Visual quarantine dialog requiring explicit user authorization for destructive or privileged commands.
* **Interactive 3D Micro-Drone Desktop Companion (`shell/drone/`, `bin/drone`)**: Three.js WebGL micro-drone companion with 7 operational states, 220×220 compact floating window runner in Electron, 25 FPS eye-tracking, and cloaking (`appear`/`disappear`).

### 7. Generative UI Cards & Native Widgets (`widgets/`)
* **Generative UI Architecture**: Dynamic QML view engine compiling structured JSON payloads from AI agents into native desktop widgets.
* **Supported Card Archetypes**: High-impact KPI `metric` cards, interactive `checklist` tasks, one-click `action` buttons, validated `required-form` inputs, and signed historical line charts.

### 8. Specialized Autonomous Departments (`department_agents/`)
* **LinkedIn Department**: 12-agent autonomous fleet powered by NVIDIA NIM for content planning, hook generation, review staging, and publishing.
* **YouTube Production Department**: Autonomous scriptwriting, title ideation, thumbnail prompt scoring, SEO tagging, and description generation.
* **API Agent Department**: Autonomous API integration, OpenAPI/JSON schema validation, safe HTTP payload generation, and endpoint monitoring.
* **CLI Agent Department**: Sandboxed terminal execution, command generation, exit-code validation, and error remediation.

### 9. Connectors & External Integrations (`connectors/`)
* **Composio Bridge**: Out-of-the-box integration with Composio tools (GitHub, Google Workspace, Slack, Jira, etc.) with automatic session admission.
* **Agent Reach Connector**: High-performance multi-platform content reader and search engine across 15+ platforms (Reddit, YouTube transcripts, GitHub issues/discussions, Twitter/X, Bilibili, Xiaohongshu) via unified tools.
* **API-Anything Bridge**: Generic REST/GraphQL connector translating conversational requests into structured HTTP invocations.

### 10. Bootable Arch Linux Live ISO & KVM Packaging (`packaging/iso/`, `packaging/vm/`)
* **Standalone Bootable ISO**: Complete Arch Linux diskless UEFI boot profile (`jarvis-welcome-x86_64.iso`) verified in KVM virtual machine environments.
* **Hyprland Auto-Launch**: Direct launch into Hyprland mounting `jarvis-core`, `jarvis-hud`, `omarchy-bar`, and `omarchy-dynamic-island` with an animated Arc Reactor welcome screen.

---

## 📁 Repository Layout

```
JARVIS OS/
├── voice/                     # Human Interaction Engine & Voice Core
│   ├── daemon.py              # Duplex live voice loop and state orchestrator
│   ├── needle_router.py       # Cactus-Needle local command router (<200ms)
│   ├── fish_speaker.py        # Fish Audio s2.1-pro hybrid TTS synthesis
│   ├── acknowledgements.py    # Situational acknowledgement dispatcher
│   ├── playback.py            # PipeWire audio sink and output buffer
│   ├── speech.py              # Silero VAD turn gating
│   └── hypr_monitor.py        # Real-time Hyprland workspace & window tracker
│
├── control/                   # Sovereign Desktop Control & Actuation
│   ├── tools.py               # Desktop actuators & tool execution engine
│   ├── wayland_keyboard.py    # Wayland keyboard simulation and receipts
│   ├── wayland_pointer.py     # Wayland pointer simulation & coordinate mapping
│   ├── parsing_service.py     # Local natural language command parsing
│   ├── execution_policy.py    # Security admission and confirmation policies
│   └── diagnostics.py         # Full-stack system doctor & auto-healing
│
├── memory/                    # Sovereign 4-Tier Memory Vault
│   ├── db.py                  # Zero-RAM SQLite driver & recursive CTE graph engine
│   ├── staleness_detector.py  # Bitemporal staleness, TTL & collision detectors
│   ├── vector_store.py        # Vector embedding store & cosine math
│   ├── hybrid.py              # Reciprocal Rank Fusion (BM25 + Vector)
│   └── obsidian.py            # Bidirectional Obsidian markdown sync
│
├── kernel/                    # Linux Kernel Driver & Self-Healing
│   ├── jarvis_dev.py          # /dev/jarvis ioctl & sysfs interface
│   ├── self_healer.py         # Zero-model-call hardware & service auto-repair
│   └── system_monitor.py      # Real-time hardware telemetry collector
│
├── harness/                   # Multi-Agent Orchestration & StateGraph
│   ├── state_graph.py         # Typed StateGraph & cyclic feedback loops
│   ├── hermes_api.py          # FastAPI REST endpoint for agent delegation
│   ├── durable_hermes.py      # Durable Hermes gateway worker
│   └── task_events.py         # Task event lifecycle contracts
│
├── shell/                     # User Interface & Desktop Shells
│   ├── launch.sh              # Quickshell Wayland desktop launcher
│   ├── ArcReactorCore.qml     # Central glowing core telemetry & acoustic visualization
│   ├── ApplicationStage.qml   # App staging & virtual workspace vault
│   ├── CommandPalette.qml     # Stable window & application spotlight launcher
│   ├── ExecutionAirlock.qml   # Destructive command quarantine overlay
│   ├── ada/                   # Ada JARVIS workspace desktop interface
│   └── drone/                 # 3D Micro-Drone companion (Three.js + Electron)
│
├── widgets/                   # Generative UI Cards & Native Widgets
│   ├── backend.py             # Widget IPC server and event dispatcher
│   ├── native_cards.py        # Schema compiler for KPI, forms, and charts
│   ├── GeneratedView.qml      # Recursive QML view engine
│   └── ViewNode.qml           # Node renderer for generative UI cards
│
├── connectors/                # External App & Service Connectors
│   ├── agent_reach.py         # Multi-platform content reader & search (Reddit, YT, X)
│   ├── composio.py            # Composio platform tool integration
│   └── api_anything.py        # Generic REST/GraphQL API connector
│
├── department_agents/         # Autonomous Specialized Departments
│   ├── linkedin/              # 12-Agent LinkedIn Department (NVIDIA NIM)
│   ├── youtube_production/    # YouTube Video Scripting & SEO Department
│   ├── api_agent/             # API Integration & Validation Agent
│   └── cli_agent/             # Autonomous Terminal Execution & Triage Agent
│
├── bin/                       # Normalized Executable CLI Binaries
│   ├── cli (jarvis)           # Unified system CLI
│   ├── voice (jarvis-voice)   # Voice daemon CLI wrapper
│   ├── control (jarvis-ctrl)  # Desktop control CLI wrapper
│   ├── memory (jarvis-mem)    # Memory vault CLI wrapper
│   ├── de (jarvis-de)         # Desktop Environment launcher
│   ├── drone (jarvis-drone)   # 3D Micro-Drone controller
│   ├── monitor (jarvis-mon)   # System monitor CLI wrapper
│   └── askpass (jarvis-askpass)# Privileged HUD password card prompter
│
├── packaging/                 # Arch Linux & Distribution Packaging
│   ├── PKGBUILD               # Arch package specification
│   ├── jarvis-de.desktop      # Wayland session desktop entry
│   ├── iso/                   # Bootable Arch Linux Live ISO build scripts
│   └── vm/                    # KVM / QEMU virtual machine test harness
│
├── scripts/                   # System Maintenance & Verification Scripts
│   ├── install.sh             # System package installer
│   ├── behavior_gate.py       # Behavior regression testing gate
│   └── mode.py                # System profile mode switcher
│
└── tests/                     # Comprehensive Pytest Test Suites (2,200+ tests)
```

---

## 🛠️ CLI Tools & Everyday Usage

JARVIS OS provides normalized binary commands in `bin/` alongside canonical `jarvis` aliases:

### Unified CLI (`cli` / `jarvis`)
```bash
# Query system status, connectivity, and active models
cli doctor
# or
jarvis doctor

# View real-time system monitor
cli monitor

# Execute desktop command directly
cli task "open firefox and navigate to github.com"
```

### Voice Core CLI (`voice` / `jarvis-voice`)
```bash
# Check dependencies and audio devices without opening streams
voice --check

# Inspect live status, latency metrics, and connection state
voice status
voice status --json

# Toggle active listening or enter low-power standby
voice listen toggle
voice standby

# Discard current speech and cancel active playback
voice listen cancel
```

### 3D Micro-Drone Companion CLI (`drone` / `jarvis drone`)
```bash
# Start the 3D micro-drone companion overlay
drone start

# Check running bridge and window status
drone status

# Cloak (disappear) or bring back (appear) the drone overlay
drone disappear
drone appear
drone toggle

# Trigger physical gestures
drone gesture nod
drone gesture roll
drone gesture recoil

# Stop drone companion
drone stop
```

### Sovereign Memory CLI (`memory` / `jarvis-memory`)
```bash
# View storage statistics and fact counts
memory stats

# Store a verified personal fact
memory store "User preferences: dark theme, 400ms turn silence, local command priority."

# Hybrid search across knowledge base
memory search "theme preferences"

# Sync with external Obsidian vault
memory sync --vault ~/Documents/Obsidian/JarvisVault
```

### Desktop Actuation CLI (`control` / `jarvis-control`)
```bash
# Run system discovery
control discovery

# Test keyboard typing receipt
control type "Hello from JARVIS OS"

# Focus specific window by title
control focus "Terminal"
```

### Multimodal Attachment & File Dispatch
```bash
# Ingest local file, PDF, or video with automatic keyframe/metadata extraction
cli send --file ~/Videos/demo.mp4 "Please analyze the visual scenes in this clip"
cli send --file ~/Documents/architecture.pdf "Summarize the key architectural decisions"
```

### Quickshell Sci-Fi Desktop Shell (`de` / `jarvis-de`)
```bash
# Launch the full JARVIS Wayland desktop session
de

# Preview the Quickshell desktop HUD
bin/hud-preview
```

---

## ⚙️ Service Management (systemd)

JARVIS OS runs as modular systemd user services:

```bash
# Install core packages and link binaries
./scripts/install.sh

# Enable and start user services
systemctl --user daemon-reload
systemctl --user enable --now voice.service
systemctl --user enable --now cli-agent.service
systemctl --user enable --now device-bridge.service
systemctl --user enable --now os-speaker.service
systemctl --user enable --now os-bridge.service

# Check service status
systemctl --user status voice.service
journalctl --user -u voice.service -f
```

---

## 🧪 Testing & Verification

JARVIS OS includes an exhaustive regression suite with over 2,200 unit and integration tests.

### 1. Run Full Python Test Suite
```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

### 2. Run Behavior Gate Checks
```bash
python scripts/behavior_gate.py --report
```

---

## 🔒 Security & Policy Boundaries

1. **Execution Admission & Airlock**: Destructive shell invocations (e.g., `rm -rf`, disk formatting, system reboot) are quarantined in the visual Quickshell Execution Airlock and require explicit confirmation.
2. **Data Protection**: Personal facts and transcripts remain in sovereign local storage (SQLite WAL + Obsidian markdown) without telemetry or third-party leakage.
3. **Local Socket Permissions**: Control sockets in `$XDG_RUNTIME_DIR/jarvis/` are restricted to mode `0600` (user-only).
