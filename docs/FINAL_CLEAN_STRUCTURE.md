# Final Normalized Directory Structure & Migration Blueprint

* **Repository:** `/home/g0pi/JARVIS OS/`
* **Target Architecture:** 10 Normalized Functional Pillars + 7 Standard Tooling Directories
* **Date:** 2026-11-26

---

## 1. Top-Level Overview

All brand prefixes (`jarvis_`, `jarvis-`, `omarchy-`) are removed from all directory and file names. The 24+ scattered root directories and loose scripts are consolidated into a clean, modular hierarchy:

```text
/home/g0pi/JARVIS OS/
├── bin/                   # System CLI wrappers and entrypoint executables
├── config/                # Static system configs, environment templates, and monitor schemas
├── control/               # Hardware/desktop actuation, Wayland input, window manager, and OS bridge
│   ├── bridge/            # D-Bus, udev, network, and Bluetooth system watchers
│   ├── connectors/        # External API and third-party integration connectors
│   └── skills/            # Desktop actuation skills (GUI control, input bar, power)
├── department_agents/     # Autonomous multi-agent departments (api, cli, google, linkedin, memory, youtube)
├── display_server/        # Wayland compositor integration, Hyprland hooks/rules, virtual outputs
├── docs/                  # Architectural documentation, designs, guides, and consolidated archives
│   ├── archive/           # Consolidated legacy documentation (formerly 'JARVIS OS DOCS')
│   └── designs/           # Design specifications and RFCs
├── harness/               # Multi-agent execution harnesses, model policy routing, durable gateways
├── kernel/                # OS substrate runtime: process supervisor, IPC message bus, monitor, self-healer
├── memory/                # Unified 4-tier memory vault: SQLite WAL, vector store, embeddings, Obsidian sync
├── packaging/             # Distribution packages, Arch PKGBUILD, VM/ISO installers
├── scripts/               # Operational tooling, install scripts, and behavior gate verification
├── shell/                 # Quickshell desktop environment UI, ArcReactor HUD, telemetry, panels, themes
├── systemd/               # User-level systemd service definitions (voice.service, os-bridge.service, etc.)
├── tests/                 # Comprehensive test suite covering all domains
├── voice/                 # Speech interaction engine: PipeWire capture, Silero VAD, Cactus/Needle router, TTS
├── widgets/               # Reactive desktop widget engine: protocols, dynamic schema, native cards, workspace
└── youtube_brain/         # Dedicated YouTube intelligence engine: transcript search, notes, topic index
```

---

## 2. Exhaustive Folder-by-Folder Breakdown

### 1. `control/` (Hardware & Desktop Actuation)
* **Source:** Merges `jarvis_control/`, `jarvis_os_bridge/`, `filesystem/`, and desktop actuation `skills/`.
* **Internal Structure:**
  ```text
  control/
  ├── bridge/                     # Formerly jarvis_os_bridge
  │   ├── bluetooth_control.py    # BlueZ D-Bus integration
  │   ├── dbus_listener.py        # System and session D-Bus event stream
  │   ├── device_watcher.py       # Udev USB and hardware device monitor
  │   ├── fs_watcher.py           # Inotify filesystem monitor
  │   ├── journal_streamer.py     # Systemd journald log streamer
  │   ├── network_control.py      # NetworkManager D-Bus integration
  │   └── service.py              # Main OS bridge daemon service
  ├── connectors/                 # Formerly connectors/
  │   ├── api_service.py          # Generic HTTP/GraphQL API executor
  │   ├── composio_bridge.py      # Composio tool integration
  │   ├── github.py               # GitHub API client
  │   └── google_workspace.py     # Google OAuth and workspace tool client
  ├── skills/                     # Formerly skills/
  │   ├── gui_control.py          # Wayland window and click skills
  │   ├── input_bar.py            # Floating input bar trigger
  │   ├── system_control.py       # Desktop brightness/volume actuators
  │   └── system_power.py         # Lock, suspend, shutdown commands
  ├── browser.py                  # Headless and automated browser actuator
  ├── device_bridge.py            # Android/mobile pairing bridge
  ├── execution_policy.py         # Shell command safety and deny list gate
  ├── evidence.py                 # Structured execution receipts collector
  ├── nlu.py                      # Local intent parser and keyword mapper
  ├── package_manager.py          # Pacman / yay system package manager
  ├── parsing_service.py          # Natural language speech-to-command worker
  ├── phone_control.py            # KDE Connect / scrcpy device controls
  ├── privileged_exec.py          # PolicyKit and sudo execution boundary
  ├── wayland_keyboard.py         # Wayland uinput virtual keyboard typing
  └── wayland_pointer.py          # Wayland uinput virtual mouse pointer
  ```

### 2. `department_agents/` (Autonomous Multi-Agent Fleets)
* **Source:** Formerly `departments/`.
* **Internal Structure:**
  ```text
  department_agents/
  ├── api_agent/                  # Dedicated REST/GraphQL API automation agent
  │   ├── department.py
  │   └── service.py
  ├── cli_agent/                  # Terminal and CLI automation agent
  │   ├── department.py
  │   └── service.py
  ├── google_workspace/           # 6-agent fleet for Gmail, Calendar, Drive, Docs, Sheets, Tasks
  │   ├── agents.py
  │   └── department.py
  ├── linkedin/                   # 12-agent autonomous fleet for B2B brand building
  │   ├── agents/
  │   └── department.py
  ├── memory/                     # Cognitive memory department (5 reasoning agents)
  │   ├── agents.py
  │   └── department.py
  └── youtube_production/         # Telugu Shorts & video production department
      ├── agents.py
      └── department.py
  ```

### 3. `display_server/` (Wayland Compositor & Display Integration)
* **Source:** Consolidates `config/hypr/`, `desktop/`, and compositor display hooks.
* **Internal Structure:**
  ```text
  display_server/
  ├── hypr/                       # Formerly config/hypr
  │   ├── hyprland.conf           # Primary Hyprland window manager rules
  │   ├── lock.conf               # Hyprlock screen configuration
  │   ├── minimal.conf            # Low-overhead compositor configuration
  │   └── bindings.lua            # Window manipulation keybindings
  ├── greetd/                     # Greetd display manager configuration
  ├── virtual_outputs.py          # Virtual Wayland display setup (headless/remote)
  └── session.sh                  # Session initialization script
  ```

### 4. `harness/` (Agent Runtime Harnesses & Model Routing)
* **Source:** Formerly `orchestration/` and `core/harness_config.py`.
* **Internal Structure:**
  ```text
  harness/
  ├── contracts/                  # Formerly contracts/
  │   └── task-event-v1.json      # Standardized task lifecycle schema
  ├── agent_orchestrator.py       # Multi-agent dispatch and execution router
  ├── durable_hermes.py           # Durable background gateway and state persistence
  ├── groq_tool_router.py         # High-speed model routing via Groq
  ├── harness2_adapter.py         # Subagent runtime harness adapter
  ├── hermes_api.py               # FastAPI REST endpoints for agent delegation
  ├── hermes_bridge.py            # Event bridge between subagents and UI
  ├── mcp_server.py               # Model Context Protocol stdio server
  ├── model_policy.py             # Model selection, quota, and fallback rules
  ├── personas.py                 # System personas and prompt styles
  ├── release_manager.py          # Blue/green release switching and health probes
  └── task_events.py              # Lifecycle notifications (start, progress, completion)
  ```

### 5. `kernel/` (Operating System Substrate Runtime)
* **Source:** Formerly `core/` + root execution runners (`agent.py`).
* **Internal Structure:**
  ```text
  kernel/
  ├── proactive/                  # Formerly proactive/
  │   ├── attention.py            # User focus and idle time detector
  │   ├── calendar.py             # Proactive schedule monitor
  │   └── system_watch.py         # Hardware resource anomaly detection
  ├── agent.py                    # Core OS agent daemon loop
  ├── background_tasks.py         # Async task supervisor and queue
  ├── config.py                   # Centralized configuration parser
  ├── env.py                      # XDG path resolution and environment loader
  ├── ipc.py                      # Local Unix domain socket IPC bus
  ├── response_metrics.py         # Telemetry latency tracking
  ├── self_healer.py              # Automated daemon health recovery agent
  ├── system_monitor.py           # CPU, RAM, battery, thermal, and network probes
  └── tool_dispatch.py            # Unified execution bus for local tools
  ```

### 6. `memory/` (Sovereign 4-Tier Memory Vault)
* **Source:** Merges `jarvis_memory/` and legacy `memory/` data.
* **Internal Structure:**
  ```text
  memory/
  ├── data/                       # Local SQLite storage and Obsidian vault mirror
  ├── bridge.py                   # External query bridge
  ├── embeddings.py               # Dense vector embeddings generator
  ├── evaluation.py               # Memory quality and recall evaluation
  ├── hybrid.py                   # Reciprocal Rank Fusion (BM25 + Cosine)
  ├── mcp_server.py               # Memory MCP stdio server
  ├── obsidian.py                 # Bidirectional Obsidian vault synchronization
  ├── paths.py                    # Standard XDG state path resolver
  ├── staleness_detector.py       # Outdated memory decay and cleanup
  ├── store.py                    # SQLite WAL ledger database engine
  └── vector_store.py             # Vector similarity indexing
  ```

### 7. `shell/` (Quickshell Desktop Environment UI)
* **Source:** Merges `ui/jarvis_shell/`, `ui/omarchy-ai.orbit/`, `quickshell/`, and `plugins/`.
* **Internal Structure:**
  ```text
  shell/
  ├── orbit/                      # Floating HUD orbit visualization
  │   ├── AuraFieldOrbit.qml
  │   └── OrbitOverlay.qml
  ├── plugins/                    # Formerly plugins/
  │   ├── voice.indicator
  │   └── voice.orb
  ├── quickshell/                 # Core Quickshell configuration and components
  │   ├── shell.qml
  │   └── Theme.qml
  ├── ApplicationStage.qml        # Active window layout and stage
  ├── ArcReactorCore.qml          # Ambient voice activity visualization
  ├── AssistantCard.qml           # Floating assistant response card
  ├── CommandPalette.qml          # Spotlight-style launcher
  ├── Desktop.qml                 # Formerly JarvisDesktop.qml
  ├── ExecutionAirlock.qml        # User approval prompt for privileged actions
  ├── HologramCard.qml            # Agent progress visualization card
  ├── HudPreview.qml              # Live desktop preview
  ├── PreviewWindow.qml           # Formerly ui/JarvisHudPreview.qml
  ├── SystemOverview.qml          # System resource telemetry panel
  ├── TasksPanel.qml              # Active background tasks drawer
  ├── Theme.qml                   # Formerly JarvisTheme.qml
  ├── TopBar.qml                  # Desktop status and workspace bar
  └── launch.sh                   # Quickshell startup script
  ```

### 8. `voice/` (Speech Interaction & Human Interaction Engine)
* **Source:** Formerly `voice_layer/` + `audio/` sound assets.
* **Internal Structure:**
  ```text
  voice/
  ├── assets/                     # Sound effects, chimes, and wake models
  │   ├── acknowledgements/       # Pre-rendered situational spoken affirmations
  │   └── sounds/                 # System auditory feedback sounds
  ├── acknowledgements.py         # Dynamic affirmative speech selector
  ├── daemon.py                   # Main PipeWire audio capture and loop
  ├── decision_router.py          # Gemini Live duplex vs Cactus-Needle offline router
  ├── fish_speaker.py             # Fish Audio local TTS synthesis engine
  ├── local_speech.py             # Kokoro / offline TTS engine
  ├── microphone.py               # PipeWire 16 kHz PCM stream reader
  ├── needle_router.py            # Sub-200ms Cactus-Needle local command recognizer
  ├── persona.py                  # System conversational voice prompt
  ├── playback.py                 # Fenced audio playback queue with instant interruption
  └── recovery.py                 # Audio device auto-reconnect and error recovery
  ```

### 9. `widgets/` (Reactive Desktop Widget Engine)
* **Source:** Merges `widget_engine/` and `ui/jarvis_widgets/`.
* **Internal Structure:**
  ```text
  widgets/
  ├── backend.py                  # Widget state and IPC daemon backend
  ├── bridge.py                   # QML-to-Python IPC bridge
  ├── native_cards.py             # Pre-built system widgets (timer, weather, agent card)
  ├── protocol.py                 # Widget JSON protocol definition
  ├── view_schema.py              # Dynamic QML view schema generator
  ├── workspace.py                # Multi-card canvas workspace manager
  ├── ActionButton.qml            # Reactive widget button component
  ├── GeneratedView.qml           # Dynamically generated schema-driven card
  ├── WidgetCard.qml              # Base interactive card container
  └── Widgets.qml                 # Main widget canvas stage
  ```

### 10. `youtube_brain/` (YouTube Intelligence Engine)
* **Source:** Consolidated from `connectors/yt_brain.py` and `skills/domains/yt_brain.py`.
* **Internal Structure:**
  ```text
  youtube_brain/
  ├── client.py                   # Query client for personal YouTube knowledge base
  ├── domain.py                   # JARVIS desktop skill adapter
  ├── history_classifier.py       # Watch history classifier
  ├── transcript_fetcher.py       # Automatic transcript downloader
  ├── summarizer.py               # Multi-stage video summarizer
  ├── note_classifier.py          # Markdown note categorization
  └── topic_index.py              # Semantic topic search index
  ```

---

## 3. Supporting Repository Infrastructure

```text
├── bin/                          # Normalized CLI wrappers
│   ├── askpass                   # Formerly jarvis-askpass
│   ├── cli                       # Formerly jarvis (main OS CLI entrypoint)
│   ├── control                   # Formerly jarvis-control
│   ├── de                        # Formerly jarvis-de (desktop environment launcher)
│   ├── hud-preview               # Formerly jarvis-hud-preview
│   ├── lock                      # Formerly jarvis-lock (screen lock launcher)
│   ├── memory                    # Formerly jarvis-memory
│   ├── monitor                   # Formerly jarvis-monitor
│   ├── shell                     # Formerly jarvis-shell
│   ├── theme-setup               # Formerly jarvis-theme-setup
│   ├── vision                    # Formerly jarvis-vision
│   ├── voice                     # Formerly jarvis-voice
│   ├── voice-toggle              # Formerly jarvis-voice-toggle
│   └── widgets                   # Formerly jarvis-widgets
├── config/                       # Static declarative configs
│   ├── config.toml.example       # Global configuration template
│   ├── monitoring.json           # Telemetry thresholds and probes
│   └── omarchy/                  # Shell themes and hook scripts
├── docs/                         # Consolidated documentation
│   ├── archive/                  # Merged legacy docs (formerly 'JARVIS OS DOCS')
│   ├── designs/                  # Architectural specs and RFCs
│   └── guides/                   # Operational and user guides
├── packaging/                    # Distribution packaging
│   ├── build-de                  # Formerly build-jarvis-de
│   ├── de                        # Desktop session wrapper
│   ├── de.desktop                # Wayland session desktop file
│   └── PKGBUILD                  # Arch Linux package build script
├── scripts/                      # Operational automation
│   ├── behavior_gate.py          # CI/CD integrity and behavior regression gate
│   ├── ci_self_heal.py           # Automated self-healing test repair
│   ├── ctl.py                    # Formerly jarvisctl.py
│   ├── install.sh                # System install script
│   ├── mode.py                   # Formerly jarvis_mode.py
│   ├── pair.py                   # Formerly jarvis_pair.py
│   └── release.py                # Formerly jarvis_release.py
├── systemd/                      # User systemd service definitions
│   ├── api-agent.service         # Formerly jarvis-api-agent.service
│   ├── cli-agent.service         # Formerly jarvis-cli-agent.service
│   ├── device-bridge.service     # Formerly jarvis-device-bridge.service
│   ├── monitor.service           # Formerly jarvis-monitor.service
│   ├── os-bridge.service         # Formerly jarvis-os-bridge.service
│   ├── os-speaker.service        # Formerly jarvis-os-speaker.service
│   ├── shell.service             # Formerly jarvis-shell.service
│   ├── voice.service             # Formerly jarvis-voice.service
│   └── widget-hud.service        # Formerly jarvis-widget-hud.service
└── tests/                        # 112+ test files with canonical imports
```

---

## 4. Complete De-Branding & Normalization Matrix

| Original Legacy Path | Normalized Target Path | Notes |
| :--- | :--- | :--- |
| `jarvis_control/` | `control/` | Wayland input and desktop actuators |
| `jarvis_os_bridge/` | `control/bridge/` | D-Bus and system event listeners |
| `core/` | `kernel/` | OS substrate runtime |
| `departments/` | `department_agents/` | Autonomous agent departments |
| `orchestration/` | `harness/` | Multi-agent execution harnesses |
| `jarvis_memory/` + `memory/` | `memory/` | Merged 4-tier memory vault |
| `ui/jarvis_shell/` | `shell/` | Quickshell desktop environment UI |
| `ui/omarchy-ai.orbit/` | `shell/orbit/` | Ambient HUD element |
| `ui/jarvis_widgets/` + `widget_engine/` | `widgets/` | Merged widget engine and views |
| `voice_layer/` + `audio/` | `voice/` | Frozen acoustic speech engine |
| `JARVIS OS DOCS/` | `docs/archive/` | Historical documentation |
| `configs/` | `config/` | Merged configuration directory |
| `ui/JarvisDesktop.qml` | `shell/Desktop.qml` | Desktop QML root |
| `ui/JarvisTheme.qml` | `shell/Theme.qml` | Desktop color and geometry tokens |
| `ui/JarvisHudPreview.qml` | `shell/PreviewWindow.qml` | Renamed to prevent collision with `shell/HudPreview.qml` |
| `bin/jarvis*` | `bin/*` | All prefixes stripped (`de`, `lock`, `voice`, etc.) |
| `scripts/jarvisctl.py` | `scripts/ctl.py` | Main management script |
| `systemd/jarvis-*.service` | `systemd/*.service` | All unit prefixes stripped |
| `agent.py` | `kernel/agent.py` | Moved from root |
| `system_control.py` | `control/skills/system_control.py` | Moved from root |
| `task_runner.py` | `control/task_runner.py` | Moved from root |
| `agent_orchestrator.py` | `harness/agent_orchestrator.py` | Moved from root |
