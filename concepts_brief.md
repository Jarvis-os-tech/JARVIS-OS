# Modular OS Architecture Restructuring (Normalized & De-Branded)

* **Author:** Gopi
* **Date:** 2026-11-26
* **Status:** Brainstorm Synthesized (Multi-Lens Goldfish Audit Complete)

## Overview

Restructure the `/home/g0pi/JARVIS OS/` repository from its current fragmented layout (24+ top-level directories, legacy root scripts, and scattered UI trees) into a clean, normalized, modular architecture. All brand prefixes and project name repetitions (specifically all `jarvis_` and `jarvis-` prefixes) are removed from directory and file names. The top level is decluttered to expose only standard functional pillars alongside repository infrastructure.

```text
/home/g0pi/JARVIS OS/
├── bin/                   # System CLI wrappers and entry scripts (de, hud-preview, lock, ctl)
├── config/                # Global declarative configurations and environment templates
├── control/               # Desktop actuation, Wayland input, window manager IPC, and execution policy
│   └── bridge/            # D-Bus, udev, network, and Bluetooth system watchers (formerly jarvis_os_bridge)
├── department_agents/     # Autonomous multi-agent departments (api, cli, google_workspace, linkedin, memory, youtube)
├── display_server/        # Wayland compositor integration, Hyprland hooks/rules, virtual outputs
├── docs/                  # Architectural documentation, designs, and historical archives
├── harness/               # Multi-agent execution harnesses, model policy routing, durable gateways, task lifecycles
├── kernel/                # OS substrate runtime: process daemon lifecycles, IPC message bus, monitor, self-healer, env
├── memory/                # Unified 4-tier memory vault: SQLite WAL, vector store, embeddings, Obsidian sync, MCP
├── packaging/             # Distribution packages, Arch PKGBUILD, VM/ISO build tooling
├── scripts/               # Operational tooling, install scripts, and behavior gate verification
├── shell/                 # Quickshell desktop UI, ArcReactor HUD, telemetry, panels, themes (formerly ui/jarvis_shell)
├── systemd/               # User-level systemd service definitions (voice.service, os-bridge.service, etc.)
├── tests/                 # Comprehensive test suite covering all domains
├── voice/                 # Speech interaction engine: PipeWire capture, Silero VAD, Cactus/Needle router, TTS
├── widgets/               # Reactive desktop widget engine: protocols, dynamic schema, native cards, workspace
└── youtube_brain/         # Dedicated YouTube intelligence engine: transcript search, notes classifier, topic index
```

---

## Analysis

### 1. Synthesized Goldfish Audit Findings

The parallel Goldfish review across 7 specialized lenses (`egm-inventive-catalyst`, `egm-design`, `egm-codebase-details`, `egm-zoom-out`, `egm-comprehension`, `egm-implementation-readiness`, and `egm-structural`) revealed several critical technical contradictions and risks in a naive file-renaming approach:

1. **The `AliasImporter` / `sys.meta_path` Bootstrap Paradox:**
   * Placing an alias importer in `kernel/__init__.py` fails whenever an external runner, standalone CLI, systemd service (`python -m voice_layer`, `python -m jarvis_control.device_bridge`), or `pytest` executes without importing `kernel` first.
   * *Resolution:* Do not rely indefinitely on dynamic runtime hooks. Implement a root `sitecustomize.py` and `tests/conftest.py` hook strictly as an atomic **transition shim**, and execute a deterministic AST import rewrite across internal tests, scripts, and packages. Ensure `sys.modules[legacy] = sys.modules[canonical]` binds to the exact same module instance to prevent double-executing singletons or loading duplicate ML models in RAM/VRAM.

2. **Non-Python Runtime Blindness (QML, Hyprland, Systemd):**
   * Python's `sys.meta_path` does not intercept QML imports (`import "jarvis_shell"`), relative JS files (`../omarchy-ai.orbit/OrbitState.js`), Hyprland `source=` directives, or `systemd` `ExecStart=` commands.
   * Moving `ui/jarvis_shell/` and renaming `JarvisTheme.qml` or `JarvisHudPreview.qml` breaks Quickshell and risks desktop/lockscreen lockout.
   * *Resolution:* Explicitly audit and update QML `qmldir`, relative JS script paths, and Hyprland config files atomically with directory moves.

3. **Daemon Availability & Self-Healer Crash Storms:**
   * Renaming systemd units while background services (`jarvis-voice.service`, `jarvis-os-bridge.service`, `jarvis-cli-agent.service`) are active creates race conditions on PipeWire and D-Bus.
   * If `system_monitor.py` or `self_healer.py` detects missing legacy unit names during cutover, it could trigger automated recovery loops and runaway LLM token burn.
   * *Resolution:* Temporarily disable automated self-healing during migration. Follow an atomic daemon stop → reload → start cutover protocol.

4. **Complete Accounting of the 24 Existing Top-Level Directories:**
   * The real codebase contains 24 top-level directories tracked by `scripts/install.sh` and `scripts/behavior_gate.py`.
   * Unaccounted directories are assigned clear, permanent homes:
     * `connectors/` → Retained as top-level integration pillar or housed in `control/connectors/`.
     * `skills/` & `skill_manifests/` → Retained or consolidated with `harness/skills/`.
     * `contracts/` → Preserved under repository root for cross-platform event schemas.
     * `learning/` & `proactive/` → Integrated into `kernel/` / `memory/` or preserved as top-level subpackages.
     * `audio/` → Recognized as an active Python compatibility shim redirecting to `voice/`, not merely static media files.
     * `filesystem/` → Integrated cleanly into `control/filesystem/` or retained as an actuation subsystem.
     * `configs/` vs `config/` → Merged into unified `config/`.

5. **Voice Subsystem Freeze & Provenance Compliance:**
   * `CLAUDE.md` documents an explicit voice subsystem freeze, and `PROVENANCE.json` tracks upstream licenses for `jarvis_control` and `voice_layer`.
   * *Resolution:* The reorganization moves directory paths (`voice_layer/` → `voice/`, `jarvis_control/` → `control/`) without altering internal acoustic algorithms, Silero VAD thresholds, or Cactus-Needle parsing logic. `PROVENANCE.json` path mappings are updated synchronously.

6. **External Data Separation (`youtube_brain/`):**
   * External repository `~/jarvis-yt-brain/` contains mutable runtime state (`kb.sqlite`, sockets, caches).
   * *Resolution:* Only pure Python connectors, skill adapters, and pipeline code are tracked inside repository `youtube_brain/`. Mutable SQLite databases and socket paths remain outside git under standard XDG paths (`~/.local/state/jarvis/`).

---

## 2. Directory & Component Mapping

| Normalized Pillar | Existing Source Subsystems | Key Responsibilities |
| :--- | :--- | :--- |
| `bin/` | `bin/jarvis*` | Normalized entrypoints (`de`, `hud-preview`, `lock`, `ctl`, `voice-toggle`). Legacy symlinks generated at install/packaging time. |
| `config/` | `config/`, `configs/` | Unified static system configuration, environment templates (`config.toml.example`), and monitoring schemas. |
| `control/` | `jarvis_control/`, `jarvis_os_bridge/`, `filesystem/` | Wayland actuation (`uinput`), Hyprland window management, D-Bus/udev listeners (`control/bridge/`), file inspection, execution policy gates. |
| `department_agents/` | `departments/` | Specialized multi-agent departments (`api_agent`, `cli_agent`, `google_workspace`, `linkedin`, `memory`, `youtube_production`). |
| `display_server/` | `config/hypr/`, display integrations | Wayland compositor integration, Hyprland window rules, lockscreen integration, virtual output configs. |
| `docs/` | `docs/`, `'JARVIS OS DOCS'`, root `*.md` | Consolidated architectural documentation, designs (`docs/designs/`), and historical archives (`docs/archive/`). |
| `harness/` | `orchestration/`, `core/harness_config.py` | Multi-agent execution harnesses, model policy routing (`groq_tool_router`), durable gateways, task event lifecycles. |
| `kernel/` | `core/` (excluding `harness_config.py`) | OS runtime substrate: daemon lifecycle, IPC message bus, `system_monitor.py`, `self_healer.py`, `background_tasks.py`, `env.py`. |
| `memory/` | `jarvis_memory/`, legacy `memory/` | Unified 4-tier memory vault: SQLite WAL ledger, vector embeddings, BM25/cosine RRF retrieval, Obsidian sync, MCP server. |
| `packaging/` | `packaging/` | Arch Linux PKGBUILD, desktop entry files, VM/ISO installation builders. |
| `scripts/` | `scripts/` | Operational scripts (`install.sh`, `behavior_gate.py`, `ci_self_heal.py`), normalized to avoid brand prefixes. |
| `shell/` | `ui/jarvis_shell/`, `ui/omarchy-ai.orbit/`, `ui/` | Quickshell desktop QML environment: HUD, TopBar, LeftNav, ArcReactor, HologramCard, SystemOverview, TasksPanel, CommandPalette, themes. |
| `systemd/` | `systemd/` | User systemd services (`voice.service`, `os-bridge.service`, `cli-agent.service`, `monitor.service`). |
| `tests/` | `tests/` | Complete 112+ file test suite covering all domains with updated import references. |
| `voice/` | `voice_layer/`, `audio/` | Ambient PipeWire capture, Silero VAD turn gating, Cactus-Needle local router, Gemini Live duplex streaming, TTS synthesis. |
| `widgets/` | `widget_engine/`, `ui/jarvis_widgets/` | Reactive desktop widget engine: IPC protocol, dynamic QML schema generator, native cards, workspace state manager. |
| `youtube_brain/` | `connectors/yt_brain.py`, `skills/domains/yt_brain.py` | YouTube intelligence: transcript retrieval, notes classifier, topic index, and scriptwriting pipeline. |

---

## Goals vs. Non-Goals

### In-Scope Goals
* Complete removal of `jarvis_` and `jarvis-` prefixes from all repository directory and file names.
* Full consolidation of split domains (`jarvis_memory` + `memory` → `memory`; `ui/jarvis_widgets` + `widget_engine` → `widgets`; `jarvis_control` + `jarvis_os_bridge` → `control`).
* Migration of root-level compatibility shims (`agent.py`, `agent_orchestrator.py`, `system_control.py`, `task_runner.py`) into their true functional packages (`kernel/`, `harness/`, `control/`).
* Archiving stray root markdown design files into `docs/designs/` and `'JARVIS OS DOCS'` into `docs/archive/`.
* Deployment of a root `sitecustomize.py` / `conftest.py` transition aliasing shim to guarantee zero test or daemon breakages.
* Full update of `scripts/install.sh`, `scripts/behavior_gate.py`, and `packaging/PKGBUILD` to track all normalized directory names.

### Out-of-Scope Non-Goals
* Altering core acoustic algorithms, Silero VAD parameters, or Cactus-Needle command tables (preserving voice subsystem freeze).
* Moving mutable runtime state, SQLite databases, or secrets from XDG paths into the git repository.
* Renaming internal conversational persona prompt strings or external third-party API keys.
* Deleting underlying git commit history (moves performed via pure `git mv`).

---

## Alternatives Weighed

1. **Cosmetic Symlink Cloaking (Symlinks in Root):**
   * *Rejected:* Leaves the repository root cluttered with 20+ legacy symlinks, defeating the objective of a clean, normalized tree.
2. **Permanent Dynamic Aliasing Hook (`sys.meta_path`):**
   * *Rejected as a permanent solution:* Obscures true imports from IDEs, linters, and type checkers. Adopted strictly as a **temporary transition bridge** during migration.
3. **Staged Atomic Migration with Codemod (Chosen):**
   * Uses git pre-flight staging, pure `git mv` commits, automated AST import rewrites across internal tests/scripts, and packaging-level alias generation. Guarantees 100% test pass rates and zero service downtime.

---

## Key Decisions & Staging Runbook

### Stage 0: Pre-Flight Isolation & State Snapshot
1. Inspect `git status` and stash/commit in-flight modifications.
2. Tag clean baseline commit: `git tag pre-restructure-baseline`.
3. Stop active user services: `systemctl --user stop jarvis-voice.service jarvis-monitor.service jarvis-os-speaker.service jarvis-device-bridge.service jarvis-api-agent.service jarvis-cli-agent.service jarvis-shell.service`.
4. Create backup snapshots of `~/.local/state/jarvis/memory/*.db`.
* **Gate 0:** Clean git status, baseline tag verified, services stopped, DB backups verified.

### Stage 1: Transition Aliasing Hook & Manifest Updates
1. Deploy `sitecustomize.py` and update `tests/conftest.py` to transparently alias legacy package names to canonical targets with single-instance module binding.
2. Update `scripts/behavior_gate.py` directory list to include both legacy and normalized pillar names.
* **Gate 1:** `pytest tests/ -q` passes 100% on the baseline tree with the aliasing hook active.

### Stage 2: Pure `git mv` Directory Relocation
1. Relocate directories using pure `git mv` (no file content changes in the same commit to preserve `git log --follow` history):
   * `voice_layer` → `voice`
   * `jarvis_control` → `control`
   * `jarvis_os_bridge` → `control/bridge`
   * `core` → `kernel`
   * `orchestration` → `harness`
   * `departments` → `department_agents`
   * `jarvis_memory` → `memory`
   * `ui/jarvis_shell` → `shell`
   * `ui/jarvis_widgets` → `widgets`
   * `JARVIS OS DOCS` → `docs/archive`
2. Commit pure moves as a discrete atomic git commit.
* **Gate 2:** `git diff --summary` shows pure renames; test suite passes via transition aliasing hook.

### Stage 3: Internal Import, QML, Script & Manifest Normalization
1. Execute AST codemod to update internal imports across `tests/`, `scripts/`, `control/`, `kernel/`, `voice/`, `memory/`, `harness/`, `department_agents/`.
2. Update QML imports and relative script paths in `shell/` and `widgets/`.
3. Update `scripts/install.sh`, `scripts/behavior_gate.py`, and `packaging/PKGBUILD`.
4. Relocate loose root scripts into their respective pillars.
* **Gate 3:** All 112+ test files pass natively; `scripts/behavior_gate.py` passes with non-empty digests across all pillars.

### Stage 4: Systemd Service Cutover & Runtime Validation
1. Install normalized systemd unit files (`voice.service`, `os-bridge.service`, `cli-agent.service`, `monitor.service`) with backward-compatible unit aliases.
2. Run `systemctl --user daemon-reload` and enable normalized services.
3. Verify live daemon health checks and desktop shell loading.
* **Gate 4:** All normalized systemd units report `active (running)`; `bin/de --check` succeeds.
