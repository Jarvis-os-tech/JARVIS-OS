# 🤖 J.A.R.V.I.S. OS — Coding Agent Instructions (Ponytail Edition)

> **Core Mandate**: 1. Understand Problem Fully $\rightarrow$ 2. Inspect Implementations via `codebase-memory-mcp` $\rightarrow$ 3. Clean Root-Cause Implementation $\rightarrow$ 4. Full Clarity Testing & Perfection.  
> **Master Reference**: [`CODEBASE_REFERENCE.md`](file:///home/g0pi/Projects/Jarvis-OS/CODEBASE_REFERENCE.md)  
> **Knowledge Graph MCP**: [`codebase-memory-mcp`](file:///home/g0pi/.local/bin/codebase-memory-mcp) (Project: `JARVIS-V0`)  

---

## ⚡ The 4-Step Mandatory Engineering Cycle

### Step 1: Gain Full Problem Clarity First
* Do not write code until you understand the exact problem, affected execution paths, and real user intent.
* Ask: *Does this feature need to exist?* Skip speculative abstractions or unused config (YAGNI).
* Never be lazy about reading: trace the end-to-end execution flow through all affected files before editing.
* Set explicit acceptance criteria to verify in Step 4.

### Step 2: Check Existing Implementations via `codebase-memory-mcp`
* Re-implementing existing helpers, utilities, or types is strictly banned slop.
* Query the knowledge graph before writing anything:
  ```bash
  codebase-memory-mcp cli search_graph --project JARVIS-V0 --query "<keyword>"
  codebase-memory-mcp cli trace_path --project JARVIS-V0 --function-name "<func>" --direction both
  ```
* If a helper or worker already exists in `server/system_controller.ts`, `brain/actuator_dispatcher.py`, `skills/native/`, or `memory/`, **reuse it directly**.

### Step 3: Clean Implementation (Polyglot Matrix & Ladder)
* Select the domain language from the Polyglot Matrix.
* Climb the Ponytail Ladder: Stop at the highest rung that holds (Reuse > Stdlib > Native > Dependencies > Shortest working diff).
* Fix root causes, not symptoms: Patch the shared handler where all callers route through.

### Step 4: Full Clarity Testing & Perfection Verification
* **Test Against Step 1 Intent**: Prove that the implementation satisfies every acceptance criterion established in Step 1.
* **Build & Verify**:
  - `npm run build:native` (compiles C++ workers, Rust audio gateway, and Rust memory engine).
  - `npm run lint` (TypeScript strict typecheck).
* **Verify Zero Regressions**: Trace callers of modified symbols with `trace_path` to guarantee sibling consumers are intact.
* **Synchronize Knowledge Graph**:
  ```bash
  codebase-memory-mcp cli index_repository --repo-path /home/g0pi/Projects/Jarvis-OS --name JARVIS-V0
  ```

---

## 🎯 Polyglot Language Hierarchy & Responsibilities

> **MANDATORY INVARIANT (Python Core vs TypeScript UI)**:  
> 1. **Core Language = Python 3.12+** (`brain/`, `main.py`): The primary core language of J.A.R.V.I.S. OS. All reasoning, Gemini Live WebSocket sessions, tool execution, actuator dispatching, subagent bridges (**Hermes**, **Ultron/OpenClaw**, **Prime**), memory vault management, 24/7 gateway daemon, and background task scheduling are written and executed in Python.  
> 2. **UI Presentation Language = TypeScript & React 19** (`ui/web/src/`): TypeScript and frontend tools are strictly and exclusively for presenting to the UI design (visual interface, Web Audio API browser capture worklet, real-time visualizers, interactive skill cards, modals, themes).  
> 3. **Strict Zero-Duplication Policy**: Never write duplicate code in Python and TypeScript to execute the same functionality. Backend actuation, system tools, and agent communication live ONLY in Python. TypeScript only consumes the Python REST / WebSocket API.  
> 4. **Execution Parity**: `npm run dev` and `python3 main.py` MUST produce the exact same operational output. Whether running `python3 main.py` or `npm run dev`, both execute the exact same unified Python Core Engine with no changes.

| Domain | Language | Subsystem Directory | When to Select | Core Constraints |
| :--- | :--- | :--- | :--- | :--- |
| **System Brain & Core Engine** | **Python 3.12+** | [`brain/`](file:///home/g0pi/Projects/Jarvis-OS/brain/)<br>[`main.py`](file:///home/g0pi/Projects/Jarvis-OS/main.py)<br>[`memory/python/`](file:///home/g0pi/Projects/Jarvis-OS/memory/python/)<br>[`tools/custom/`](file:///home/g0pi/Projects/Jarvis-OS/tools/custom/) | **Primary core language.** Gemini Live WebSocket sessions, prompt engineering (`system_prompt.j2`), actuator dispatcher, subagent bridges (**Hermes**, **Ultron**, **Prime**), memory vault, 24/7 gateway. | Asyncio-first (`async def`). Strict type hints (`pydantic`, `typing`). Port 8000. Sole source of truth for execution logic. |
| **User Interface & Presentation** | **TypeScript (React 19)** | [`ui/web/src/`](file:///home/g0pi/Projects/Jarvis-OS/ui/web/src/) | **Strictly UI design presentation only.** Visual interface, Web Audio API capture (`pcm-capture-processor.js`), live visualizer, interactive skill cards (`SkillDisplayCard.tsx`), modals. | React 19 functional components with hooks. Zero duplicate backend logic. Consumes Python API on port 8000. |
| **OS & Hardware Actuation** | **C++17** | [`skills/native/src/`](file:///home/g0pi/Projects/Jarvis-OS/skills/native/src/) | Direct hardware queries (`/proc`, `/sys`, thermals, battery, DMI), Hyprland window tiling, PipeWire recovery, sub-5ms local actions. | Single `.cpp` file. Output JSON to `stdout`. Compile via `skills/native/Makefile`. Zero cloud calls. Dispatched by Python. |
| **Audio & Memory Engine** | **Rust** | [`gateway/audio_rust/`](file:///home/g0pi/Projects/Jarvis-OS/gateway/audio_rust/)<br>[`memory/engine/`](file:///home/g0pi/Projects/Jarvis-OS/memory/engine/) | Zero-GC 16kHz/24kHz PipeWire audio streaming (`/tmp/jarvis_audio.sock`), SQLite WAL persistence, FTS5 search, hierarchical context tree buffers (`CascadeSealer`). | Tokio + Axum. Zero allocations in hot audio loops. Port 50051 for Memory engine. Bridged to Python. |
| **System Services** | **Bash** | [`gateway/services/`](file:///home/g0pi/Projects/Jarvis-OS/gateway/services/) | Systemd service units (`jarvis-gateway.service`), setup scripts. | Must include `set -euo pipefail`. Fully idempotent. |

---

## 🚫 Hard Invariants

1. **Python Core Primacy**: Python is the sole core execution language. TypeScript is strictly for the frontend UI design presentation.
2. **Zero Code Duplication**: Never write duplicate logic across Python and TypeScript to execute the same functionality. Build everything in a clear, structured order.
3. **Execution Parity**: `npm run dev` and `python3 main.py` must produce identical output and run the same unified stack.
4. Never install heavy OS scraping packages (`systeminformation`, `psutil`) when C++ workers exist.
5. Never load local LLM model weights into physical RAM.
6. Never block the event loop or audio stream with synchronous delays.
7. Never hardcode credentials or secrets.
8. Never run `git push` without explicit instruction from the user.
