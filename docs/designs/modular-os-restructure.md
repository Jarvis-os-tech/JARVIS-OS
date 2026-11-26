# Modular OS Architecture Restructuring (Normalized & De-Branded)

*   **Author:** Gopi
*   **Status:** Approved Draft / Implementation Ready
*   **Date:** 2026-11-26

--------------------------------------------------------------------------------

## Overview

This project restructures the repository into a clean, normalized, modular operating system hierarchy. It eliminates project name repetition and brand prefixes (specifically all `jarvis_` and `jarvis-` prefixes) from folder names, file names, and internal module paths. The repository top level is decluttered to expose only standard functional pillars alongside core development and packaging infrastructure.

The target directory layout establishes clear separation between low-level OS substrate runtime (`kernel/`), hardware and desktop actuation (`control/`), speech interaction (`voice/`), persistent memory storage (`memory/`), display protocol management (`display_server/`), desktop UI (`shell/`), interactive cards (`widgets/`), execution harnesses (`harness/`), autonomous departments (`department_agents/`), and media intelligence (`youtube_brain/`).

--------------------------------------------------------------------------------

## The Problem

The repository currently exhibits severe structural sprawl and naming debt that increases cognitive load and complicates maintenance:
1. **Pervasive Brand Prefix Noise:** Subsystems alternate arbitrarily between prefixes (`jarvis_control`, `jarvis_memory`, `jarvis_os_bridge`, `jarvis_shell`, `jarvis_widgets`, `jarvis-de`, `JarvisDesktop.qml`) and generic names (`voice_layer`, `core`, `departments`, `orchestration`, `ui`, `widget_engine`).
2. **Top-Level Clutter:** Root contains over 24 directories and legacy script shims (`agent.py`, `agent_orchestrator.py`, `system_control.py`, `task_runner.py`) that obscure true subsystem boundaries.
3. **Subsystem Splitting:** Memory is split between legacy `memory/` and active `jarvis_memory/`; desktop control is fragmented across `jarvis_control/`, `jarvis_os_bridge/`, and `filesystem/`; UI is fragmented across `ui/jarvis_shell/`, `ui/omarchy-ai.orbit/`, `ui/jarvis_gui/`, and `ui/jarvis_drone/`.
4. **Fragile Runtime Coupling:** Active background daemons (`jarvis-voice.service`, `jarvis-os-bridge.service`, `jarvis-cli-agent.service`), packaging scripts (`PKGBUILD`), and test suites directly depend on legacy names. Direct, uncoordinated renames cause cascading import failures and runtime crashes.

--------------------------------------------------------------------------------

## Goals

*   **Complete De-Branding of Paths:** Eliminate all `jarvis_` and `jarvis-` prefixes from folder and file names across the repository.
*   **Establish 10 Normalized Functional Pillars:** Group codebase assets into `control/`, `department_agents/`, `display_server/`, `harness/`, `kernel/`, `memory/`, `shell/`, `voice/`, `widgets/`, and `youtube_brain/`.
*   **Preserve Clean Top-Level Structure:** Retain only the 10 functional pillars alongside standard repository infrastructure directories (`bin/`, `config/`, `docs/`, `packaging/`, `scripts/`, `systemd/`, `tests/`).
*   **Consolidate Split Domains:** Merge `jarvis_memory/` and `memory/` into `memory/`; merge `widget_engine/` and `ui/jarvis_widgets/` into `widgets/`; integrate `jarvis_os_bridge/` into `control/bridge/`.
*   **Zero-Downtime Migration:** Implement a transient import aliasing shim (`sitecustomize.py` / `conftest.py`) that binds canonical module instances so all 112+ test files pass and running daemons remain operational throughout the migration.
*   **Respect Voice Subsystem Freeze:** Preserve the internal acoustic pipeline, Silero VAD parameters, and Cactus-Needle command routing without regressions, updating `PROVENANCE.json` path mappings in lockstep.

--------------------------------------------------------------------------------

## Non-Goals

*   **Altering Core Voice Algorithms:** No changes to audio sample rates, Silero VAD turn gating logic, or speech synthesis pipelines.
*   **Tracking Mutable External State in Git:** No copying of SQLite databases (`kb.sqlite`), sockets, or private user OAuth credentials from `~/jarvis-yt-brain/` or `~/.local/state/` into the git tree.
*   **Renaming Conversational Voice Persona Strings:** Conversational persona identifiers (e.g. system voice character prompts) remain unchanged.
*   **Permanent Dynamic Aliasing:** The `sys.meta_path` alias hook is not a permanent architecture layer; it is strictly a staged migration bridge with a defined removal gate after internal AST import rewriting.
*   **Rewriting Test Logic:** Existing unit and integration test assertions are preserved; only import references are updated.

--------------------------------------------------------------------------------

## Open Questions

*   **Question 1 (CLI Canonical Name):** Should `bin/jarvis` be renamed to `bin/osctl` or `bin/ctl` with a packaging-generated `jarvis` alias, or retained as an explicit exception in `bin/`?
*   **Question 2 (Connectors and Skills Placement):** Should `connectors/` and `skills/` remain as distinct top-level integration directories or be nested under `control/connectors` and `harness/skills`?

--------------------------------------------------------------------------------

## Critical User Journeys (CUJs)

### CUJ 1: Developer Runs Entire Test Suite During Migration

*   **Given:** The repository directories have been renamed to their normalized paths (`control/`, `kernel/`, `voice/`, `memory/`, etc.).
*   **When:** A developer or CI pipeline runs `pytest tests/`.
*   **Then:** All test files execute and pass without `ModuleNotFoundError` or duplicate module execution, utilizing canonical imports or transition shims transparently.

### CUJ 2: User Starts Desktop Environment After Migration

*   **Given:** The user logs in via the display manager or executes `bin/de`.
*   **When:** The Wayland compositor initializes and launches the desktop shell.
*   **Then:** The Quickshell UI launches from `shell/`, loads all panels and HUD widgets without QML import failures, and communicates with `control/` and `voice/` services without errors.

### CUJ 3: Background Systemd Daemons Cut Over Cleanly

*   **Given:** Existing user services (`jarvis-voice.service`, `jarvis-os-bridge.service`) are active.
*   **When:** The user executes the Stage 4 cutover command.
*   **Then:** Old services stop cleanly, new services (`voice.service`, `os-bridge.service`) reload and start without socket or device lock contention, and `systemctl --user is-active` reports running.

--------------------------------------------------------------------------------

## Technical Plan (Architecture)

### 1. Subsystem Architecture & Layered Hierarchy

The operating system adopts an acyclic, layered architecture separating core hardware substrate, application execution, persistent memory, and presentation layers:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Desktop Presentation & UI Layer                       │
│     shell/ (Quickshell HUD, TopBar, Orbit)  │  widgets/ (Cards, Dynamic Views)│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                      Interaction & Actuation Services                       │
│      voice/ (PipeWire, VAD, TTS)     │  control/ (Wayland uinput, Hyprland) │
│                                      │  control/bridge/ (D-Bus, udev)       │
└──────────────────────┬───────────────┴──────────────────────┬───────────────┘
                       │                                      │
┌──────────────────────▼──────────────────────────────────────▼───────────────┐
│                          Core OS Runtime Substrate                          │
│                                   kernel/                                   │
│    (Daemon Supervision, IPC Message Bus, System Monitor, Self-Healer, Env)   │
└──────────────────────┬──────────────────────────────────────┬───────────────┘
                       │                                      │
┌──────────────────────▼───────────────┐      ┌───────────────▼───────────────┐
│     Knowledge & Intelligence Vault   │      │        Execution Plane        │
│                memory/               │      │            harness/           │
│ (SQLite WAL, Vector Store, RRF, MCP) │      │ (Model Routing, Durable Gates)│
│            youtube_brain/            │      │       department_agents/      │
│  (Transcripts, Topics, Scripting)    │      │ (Specialized Autonomous Fleets)│
└──────────────────────────────────────┘      └───────────────────────────────┘
```

### 2. Functional Pillar Boundaries & Contracts

1. **`kernel/` (Operating System Substrate):**
   * *Responsibilities:* Daemon lifecycle supervision, local IPC message routing, `system_monitor.py` telemetry probes, `self_healer.py` anomaly repair, and centralized environment variable loading (`env.py`).
   * *Invariants:* Strictly low-level substrate. `kernel/` never imports from `department_agents/` or `shell/`.
2. **`control/` (Hardware & Desktop Actuation):**
   * *Responsibilities:* Wayland input emulation (`uinput` keyboard and pointer), Hyprland window tiling and workspace manipulation, natural language intent parsing, execution policy gating, and action evidence recording.
   * *`control/bridge/`:* Dedicated subpackage (formerly `jarvis_os_bridge`) providing zero-polling D-Bus monitoring, udev device tracking, network status, and Bluetooth management.
3. **`voice/` (Human Interaction & Speech Engine):**
   * *Responsibilities:* Continuous PipeWire audio capture (16 kHz PCM), local Silero VAD turn gating, sub-200ms Cactus-Needle offline command routing, duplex Gemini Live streaming, situational spoken acknowledgements, and TTS synthesis (Fish Audio, Kokoro, local speech).
   * *Invariants:* Preserves all frozen acoustic parameters, audio formats, and command tables without alteration.
4. **`display_server/` (Wayland Compositor Integration):**
   * *Responsibilities:* Hyprland session startup, window rules, lockscreen integration (`bin/lock`), virtual output configuration, and compositor IPC hooks.
5. **`shell/` (Desktop Environment UI):**
   * *Responsibilities:* Quickshell QML desktop shell: ArcReactor HUD, LeftNav, TopBar, AssistantCard, HologramCard, SystemOverview, TasksPanel, CommandPalette, and desktop themes (`Theme.qml`, `Desktop.qml`).
6. **`widgets/` (Reactive Desktop Widget Engine):**
   * *Responsibilities:* Widget protocol (`protocol.py`, `bridge.py`), dynamic QML schema generation (`view_schema.py`, `GeneratedView.qml`), native cards (`native_cards.py`), and interactive workspace state manager.
7. **`memory/` (Sovereign 4-Tier Memory Vault):**
   * *Responsibilities:* SQLite WAL knowledge base, vector embeddings cache, BM25 + cosine Reciprocal Rank Fusion retrieval, Obsidian vault bidirectional sync, MCP server, and staleness detection.
8. **`harness/` (Agent Execution & Model Routing):**
   * *Responsibilities:* Subagent execution harnesses, model policy routers (`groq_tool_router.py`), durable gateway workers (`durable_hermes.py`), task event lifecycles (`task_events.py`), and evaluation runners.
9. **`department_agents/` (Autonomous Agent Fleets):**
   * *Responsibilities:* Specialized multi-agent departments (`api_agent`, `cli_agent`, `google_workspace`, `linkedin`, `memory`, `youtube_production`), department leads, and service-bounded tool allowlists.
10. **`youtube_brain/` (YouTube Intelligence Engine):**
    * *Responsibilities:* Watched-video transcript search, note classification, topic index, and Telugu scriptwriting pipeline adapter. Pure code and adapters only; persistent database state remains in XDG user data paths.

### 3. Transparent Transition Aliasing Engine (`sitecustomize.py`)

To eliminate runtime breakage while preserving clean filesystem paths, an import aliasing engine is deployed via root `sitecustomize.py` and `tests/conftest.py`:

```python
# sitecustomize.py - Canonical Single-Instance Import Aliasing Engine
import sys
import importlib
import importlib.abc
import importlib.util

ALIASES = {
    "voice_layer": "voice",
    "jarvis_control": "control",
    "jarvis_os_bridge": "control.bridge",
    "jarvis_memory": "memory",
    "core": "kernel",
    "departments": "department_agents",
    "orchestration": "harness",
    "widget_engine": "widgets",
}

class CanonicalAliasImporter(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        for old_prefix, new_prefix in ALIASES.items():
            if fullname == old_prefix or fullname.startswith(old_prefix + "."):
                canonical_name = new_prefix + fullname[len(old_prefix):]
                canonical_mod = importlib.import_module(canonical_name)
                # Ensure single-instance module binding across both names
                sys.modules[fullname] = canonical_mod
                if "." in fullname:
                    parent_old, attr = fullname.rsplit(".", 1)
                    if parent_old in sys.modules:
                        setattr(sys.modules[parent_old], attr, canonical_mod)
                return getattr(canonical_mod, "__spec__", None)
        return None

sys.meta_path.insert(0, CanonicalAliasImporter())
```

*Key Properties:*
* **Single Module Identity:** Binds `sys.modules[legacy_name] = sys.modules[canonical_name]`, preventing double-initialization of singletons, SQLite WAL connections, or Silero VAD weights.
* **Hermetic Invocation:** Operates under standard Python execution (`python -m ...`), `pytest --import-mode=importlib`, and subprocess environments without requiring hardcoded imports in `kernel/__init__.py`.
* **Deprecation Tracking:** Logs structured deprecation notices when legacy paths are accessed, allowing targeted AST rewriting before removal.

### 4. Non-Python Asset Path Resolution

* **QML Import Resolution:**
  * In `shell/HudPreview.qml`, update relative import paths from `../jarvis_widgets/` to `../widgets/` and `../omarchy-ai.orbit/` to `./orbit/`.
  * Flatten UI components into `shell/` while renaming `ui/JarvisHudPreview.qml` to `shell/PreviewWindow.qml` to avoid collision with `ui/jarvis_shell/HudPreview.qml`.
* **Compositor & Session Scripts:**
  * Update `bin/lock` to reference `display_server/hypr/lock.conf`.
  * Update `bin/de` and `packaging/de.desktop` to launch `shell/launch.sh`.
* **Systemd Unit Cutover:**
  * Deploy normalized unit files: `voice.service`, `os-bridge.service`, `cli-agent.service`, `monitor.service`, `shell.service`.
  * Provide `[Install] Alias=jarvis-voice.service` directives to ensure backward compatibility with existing systemctl invocations.

--------------------------------------------------------------------------------

## Alternatives Considered

### Alternative A: Immediate Bulk File Moves Without Transition Aliasing (Big Bang)

*   **Pros:** Requires no intermediate aliasing scripts or transition hooks; immediately establishes the final disk structure.
*   **Cons:** Breaks all 112+ test files simultaneously; crashes running systemd background services; causes unmanageable diff collisions with 50+ uncommitted files; breaks Quickshell UI imports; destroys Git rename lineage if moves and edits are mixed.
*   **Reason for Rejection:** Rejected by author: causes severe service downtime, breaks the CI behavior gate, and introduces untraceable regressions across the operating system.

### Alternative B: Permanent Root Symlinks for Legacy Paths

*   **Pros:** Retains filesystem path backward compatibility for external callers without requiring Python `sys.meta_path` hooks.
*   **Cons:** Directly violates the primary user requirement of a clean, normalized repository root; leaves over 20 legacy symlinks cluttering `ls /home/g0pi/JARVIS OS/`; preserves brand noise in directory listings.
*   **Reason for Rejection:** Rejected by author: fails to achieve the clean directory structure requested by the user.

### Alternative C: Indefinite Dynamic `sys.meta_path` Aliasing in `kernel/__init__.py`

*   **Pros:** Minimal upfront file editing; redirects imports dynamically.
*   **Cons:** Fails whenever modules are run directly (`python -m voice_layer`) before `kernel` is imported; permanently obscures canonical module paths from IDEs, linters, and type checkers; risks module duplicate initialization if `sys.modules` identity is not unified.
*   **Reason for Rejection:** Rejected by author: introduces permanent technical debt and split-brain module state. Dynamic aliasing is adopted strictly as a temporary migration phase leading to a clean AST import rewrite.

--------------------------------------------------------------------------------

## Non-Functional Requirements

### 1. Security & Privacy
*   **Secret & Credential Isolation:** No API keys, OAuth tokens, or `.env` files may be exposed or moved into public repository paths. External YouTube OAuth tokens remain isolated in XDG data directories.
*   **Execution Policy Gate:** Actuator commands passing through `control/` maintain existing execution boundary checks, denied shell patterns, and confirmation words for destructive actions.

### 2. Performance & Memory Economics
*   **Single-Instance Module Binding:** Transition aliasing must strictly deduplicate `sys.modules` references to prevent loading duplicate copies of ML models (Silero VAD, sentence embeddings) or opening competing SQLite WAL file locks, preventing RAM/VRAM exhaustion.
*   **Sub-Second Local Actuation:** Reorganizing directory paths must introduce zero latency overhead into the sub-200ms Cactus-Needle local command router.

### 3. Reliability & Rollback
*   **Zero Test Regressions:** All 112+ test files must pass across every stage of the migration.
*   **Deterministic Rollback:** The migration runbook must provide atomic rollback commands at every gate via Git baseline tags and SQLite database backups.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

### Target Files to Create, Move & Modify

#### 1. `sitecustomize.py` (Create)
*   **Type / Scope:** Python Runtime Bootstrapper (Repository Root)
*   **Proposed Changes:** Implement `CanonicalAliasImporter` with `sys.modules` single-instance binding for `voice_layer`, `jarvis_control`, `jarvis_os_bridge`, `jarvis_memory`, `core`, `departments`, `orchestration`, and `widget_engine`. Provides zero-breakage backward compatibility during migration.

#### 2. `tests/conftest.py` (Modify)
*   **Type / Scope:** Pytest Configuration Hook
*   **Proposed Changes:** Ensure root `sitecustomize.py` is loaded prior to test collection under `--import-mode=importlib`, enabling tests to resolve both legacy and canonical package imports seamlessly.

#### 3. Core Directory Relocations via Pure `git mv` (Move)
*   `voice_layer/` → `voice/` (Python speech core)
*   `jarvis_control/` → `control/` (Desktop actuators & execution policy)
*   `jarvis_os_bridge/` → `control/bridge/` (D-Bus, udev, network listeners)
*   `core/` → `kernel/` (Operating system substrate)
*   `orchestration/` → `harness/` (Agent execution harnesses & routers)
*   `departments/` → `department_agents/` (Autonomous multi-agent departments)
*   `jarvis_memory/` + `memory/` → `memory/` (Consolidated 4-tier memory package)
*   `ui/jarvis_shell/` → `shell/` (Quickshell desktop environment UI)
*   `ui/omarchy-ai.orbit/` → `shell/orbit/` (Desktop orbit HUD element)
*   `ui/jarvis_widgets/` + `widget_engine/` → `widgets/` (Widget engine & QML views)
*   `ui/JarvisHudPreview.qml` → `shell/PreviewWindow.qml` (Avoids collision with `shell/HudPreview.qml`)
*   `ui/JarvisTheme.qml` → `shell/Theme.qml`
*   `ui/JarvisDesktop.qml` → `shell/Desktop.qml`
*   `JARVIS OS DOCS/` → `docs/archive/` (Consolidated legacy documentation)

#### 4. Root Script Relocations (Move & Refactor)
*   `agent.py` → `kernel/agent_cli.py` (Main agent runner)
*   `agent_orchestrator.py` → `harness/agent_orchestrator.py`
*   `system_control.py` → `control/system_control.py`
*   `task_runner.py` → `control/task_runner.py`
*   Root markdown notes (`concepts_brief.md`, `jarvis-de-brainstorm.md`, etc.) → `docs/designs/`

#### 5. `scripts/behavior_gate.py` (Modify)
*   **Type / Scope:** CI/CD Integrity Gate
*   **Proposed Changes:** Update `source_digest()` directory tuple to include all new normalized pillars (`kernel`, `control`, `voice`, `memory`, `harness`, `shell`, `widgets`, `department_agents`, `display_server`, `youtube_brain`) while retaining legacy paths during transition.

#### 6. `scripts/install.sh` & `packaging/PKGBUILD` (Modify)
*   **Type / Scope:** Build & Installation Automation
*   **Proposed Changes:** Update package directory copy manifests, binary wrappers, and desktop session entrypoints (`de.desktop`) to reference normalized paths. Generate legacy symlinks at install time in `~/.local/bin/`.

#### 7. `systemd/*.service` (Create & Modify)
*   **Type / Scope:** Systemd User Units
*   **Proposed Changes:** Provide normalized service unit files (`voice.service`, `os-bridge.service`, `cli-agent.service`, `monitor.service`, `shell.service`) with `[Install] Alias=` directives for backward compatibility.

---

### Step-by-Step Staged Execution Runbook

#### Stage 0: Pre-Flight Hygiene & Safety Baseline
1. Commit or stash current uncommitted modifications to ensure clean Git state.
2. Tag baseline commit: `git tag pre-restructure-baseline`.
3. Stop active systemd daemons:
   ```bash
   systemctl --user stop jarvis-voice.service jarvis-monitor.service jarvis-os-speaker.service jarvis-device-bridge.service jarvis-api-agent.service jarvis-cli-agent.service jarvis-shell.service
   ```
4. Back up SQLite memory ledgers:
   ```bash
   mkdir -p ~/.local/state/jarvis/backup && cp -a ~/.local/state/jarvis/memory/*.db* ~/.local/state/jarvis/backup/
   ```
* **Gate 0:** Working tree clean (`git status`), baseline tagged, user daemons inactive, DB backups verified.

#### Stage 1: Transition Aliasing Hook & Gate Updates
1. Deploy `sitecustomize.py` and update `tests/conftest.py`.
2. Update directory list in `scripts/behavior_gate.py`.
* **Gate 1:** Run `pytest tests/ -q`; 100% of test suites pass with aliasing hook active.

#### Stage 2: Pure `git mv` Directory Relocation
1. Execute pure `git mv` commands for all primary packages and UI directories.
2. Commit pure renames as a single discrete Git commit: `git commit -m "refactor: relocate packages to normalized top-level pillars"`.
* **Gate 2:** `git diff --summary` shows pure renames without content modifications; `pytest tests/ -q` passes 100%.

#### Stage 3: Internal Import Normalization & Manifest Updates
1. Perform AST import codemod across `tests/`, `scripts/`, `kernel/`, `control/`, `voice/`, `memory/`, `harness/`, `department_agents/`.
2. Update QML relative script imports and Hyprland config references.
3. Update `scripts/install.sh`, `scripts/jarvis_mode.py`, and `packaging/PKGBUILD`.
4. Relocate root scripts and design documents into subpackages.
* **Gate 3:** All 112+ test files pass natively without shims; `python scripts/behavior_gate.py` passes with valid digests.

#### Stage 4: Systemd Service Cutover & Runtime Verification
1. Cleanly disable legacy systemd units in `~/.config/systemd/user/`.
2. Install normalized unit files (`voice.service`, `os-bridge.service`, etc.) and reload systemd:
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable --now voice.service os-bridge.service monitor.service
   ```
3. Run runtime health verification:
   ```bash
   systemctl --user is-active voice.service os-bridge.service monitor.service
   bin/de --check
   ```
* **Gate 4:** All normalized units active (running); desktop environment checks pass.

---

## Verification Plan

### 1. Automated Test Suite
*   **Command:** `pytest tests/`
*   **Success Metric:** 100% pass rate across all 112+ test files (over 2,100 unit and integration tests).

### 2. CI Behavior Regression Gate
*   **Command:** `python scripts/behavior_gate.py --report /tmp/gate_verification.json`
*   **Success Metric:** `"passed": true`, `"source_unchanged": true`, with valid non-empty SHA-256 hashes for all normalized pillars.

### 3. Service Daemon & IPC Verification
*   **Command:**
    ```bash
    systemctl --user status voice.service os-bridge.service monitor.service
    python -B -m control.device_bridge --help
    python -B -m voice --help
    ```
*   **Success Metric:** Services running without restart loops; zero D-Bus or PipeWire device contention errors.

### 4. Desktop Shell QML Verification
*   **Command:** `bin/de --check` and `quickshell --path shell/Theme.qml --check`
*   **Success Metric:** Clean compilation of all QML components; zero unresolved relative import warnings.

--------------------------------------------------------------------------------

<!-- Provenance: Indicates initial structural drafting via EGM. -->

*Drafted with EGM*
