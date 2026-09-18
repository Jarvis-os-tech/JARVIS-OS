---
trigger: always_on
description: 4-phase coding agent protocol: Problem Clarity, MCP Reconnaissance, Clean Implementation, and Full Clarity Testing.
---

# 🛡️ JARVIS-OS — Coding Agent Protocol & Language Matrix

> **Core Philosophy**: Ponytail Minimalism (Efficiency over Slop)  
> **Master Reference**: [`CODEBASE_REFERENCE.md`](file:///home/g0pi/Projects/Jarvis-OS/CODEBASE_REFERENCE.md)  
> **Knowledge Graph MCP**: [`codebase-memory-mcp`](file:///home/g0pi/.local/bin/codebase-memory-mcp) (Project: `JARVIS-V0`)  

---

## 🔍 Phase 1: Problem Comprehension (Understand Before Coding)

Never rush into code generation. The best code is code never written.

1. **Understand the Real Goal**: Identify what is actually needed versus what is speculative. Apply YAGNI ruthlessly.
2. **Trace the End-to-End Flow**: Read the affected files completely. Understand every layer the request touches (UI $\rightarrow$ Express Gateway $\rightarrow$ Brain / Native Worker $\rightarrow$ Memory).
3. **Establish Acceptance Criteria**: Formulate the exact criteria against which the final implementation will be tested in Phase 4.

---

## 🧠 Phase 2: Codebase Memory MCP Reconnaissance (Look Before You Write)

Re-implementing logic that already exists in JARVIS-OS is strictly prohibited. Before writing a single function, inspect what is already implemented:

```bash
# 1. Check if similar functions, classes, or helpers exist:
codebase-memory-mcp cli search_graph --project JARVIS-V0 --query "<function_or_concept>"

# 2. Check callers and callees of affected components:
codebase-memory-mcp cli trace_path --project JARVIS-V0 --function-name "<symbol>" --direction both

# 3. Read exact existing implementation snippets:
codebase-memory-mcp cli get_code_snippet --project JARVIS-V0 --symbol "<qualified_symbol>"
```

* **Already in the codebase?** Reuse the helper, type, or worker directly.
* **Already in stdlib or installed dependencies?** Use it. Never add an unnecessary package for what a few lines can achieve.

---

## 🎯 Phase 3: Clean Implementation (Language Hierarchy & Zero Duplication)

> **MANDATORY INVARIANT (Python Core vs TypeScript UI)**:  
> 1. **Core Language = Python 3.12+** (`brain/`, `main.py`): The primary core language of J.A.R.V.I.S. OS. All reasoning, Gemini Live WebSocket sessions, tool execution, actuator dispatching, subagent bridges (**Hermes**, **Ultron/OpenClaw**, **Prime**), memory vault management, 24/7 gateway daemon, and background task scheduling are written and executed in Python.  
> 2. **UI Presentation Language = TypeScript & React 19** (`ui/web/src/`): TypeScript and frontend tools are strictly and exclusively for presenting to the UI design (visual interface, Web Audio API browser capture worklet, real-time visualizers, interactive skill cards, modals, themes).  
> 3. **Strict Zero-Duplication Policy**: Never write duplicate code in Python and TypeScript to execute the same functionality. Backend actuation, system tools, and agent communication live ONLY in Python. TypeScript only consumes the Python REST / WebSocket API.  
> 4. **Execution Parity**: `npm run dev` and `python3 main.py` MUST produce the exact same operational output. Whether running `python3 main.py` or `npm run dev`, both execute the exact same unified Python Core Engine with no changes.

Match your feature to the exact subsystem and domain:

| Domain | Language | Subsystem Directory | When to Select | Hard Invariants |
| :--- | :--- | :--- | :--- | :--- |
| **System Brain & Core Engine** | **Python 3.12+** | [`brain/`](file:///home/g0pi/Projects/Jarvis-OS/brain/)<br>[`main.py`](file:///home/g0pi/Projects/Jarvis-OS/main.py)<br>[`memory/python/`](file:///home/g0pi/Projects/Jarvis-OS/memory/python/)<br>[`tools/custom/`](file:///home/g0pi/Projects/Jarvis-OS/tools/custom/) | **Primary core language.** Gemini Live WebSocket sessions, prompt engineering (`system_prompt.j2`), actuator dispatcher, subagent bridges (**Hermes**, **Ultron**, **Prime**), memory vault, 24/7 gateway. | Asyncio-first (`async def`). Strict type hints (`pydantic`, `typing`). Port 8000. Sole source of truth for execution logic. |
| **User Interface & Presentation** | **TypeScript (React 19)** | [`ui/web/src/`](file:///home/g0pi/Projects/Jarvis-OS/ui/web/src/) | **Strictly UI design presentation only.** Visual interface, Web Audio API capture (`pcm-capture-processor.js`), live visualizer, interactive skill cards (`SkillDisplayCard.tsx`), modals. | React 19 functional components with hooks. Zero duplicate backend logic. Consumes Python API on port 8000. |
| **OS & Hardware Actuation** | **C++17** | [`skills/native/src/`](file:///home/g0pi/Projects/Jarvis-OS/skills/native/src/) | Direct hardware queries (`/proc`, `/sys`, thermals, battery, DMI), Hyprland window tiling, PipeWire recovery, sub-5ms local actions. | Single `.cpp` file. Output JSON to `stdout`. Compile via `skills/native/Makefile`. Zero cloud calls. Dispatched by Python. |
| **Audio & Memory Engine** | **Rust** | [`gateway/audio_rust/`](file:///home/g0pi/Projects/Jarvis-OS/gateway/audio_rust/)<br>[`memory/engine/`](file:///home/g0pi/Projects/Jarvis-OS/memory/engine/) | Zero-GC 16kHz/24kHz PipeWire audio streaming (`/tmp/jarvis_audio.sock`), SQLite WAL persistence, FTS5 search, hierarchical context tree buffers (`CascadeSealer`). | Tokio + Axum. Zero allocations in hot audio loops. Port 50051 for Memory engine. Bridged to Python. |
| **System Services** | **Bash** | [`gateway/services/`](file:///home/g0pi/Projects/Jarvis-OS/gateway/services/) | Systemd service units (`jarvis-gateway.service`), setup scripts. | Must include `set -euo pipefail`. Fully idempotent. |

* **Shortest Working Diff**: No unrequested abstractions, no speculative config, no boilerplate.
* **Root-Cause Fixes**: When fixing bugs, trace common handlers with `trace_path` and fix the shared root cause.

---

## 🧪 Phase 4: Full Clarity Testing & Perfection Verification

Never finish a task without rigorously proving that what was implemented matches the full clarity established in Phase 1:

1. **Verify Against Phase 1 Requirements**:
   - Compare the output and behavior directly against the initial user intent and edge cases.
   - Confirm zero unrequested abstractions or side effects were introduced.
2. **Execute Multi-Tier Build & Linters**:
   * C++ $\rightarrow$ `npm run build:cpp`
   * Rust Memory $\rightarrow$ `npm run build:memory`
   * Rust Audio $\rightarrow$ `npm run build:gateway`
   * All Native $\rightarrow$ `npm run build:native`
   * TypeScript / UI $\rightarrow$ `npm run lint`
3. **Validate Call-Chain Integrity**:
   - Trace callers of touched components to guarantee existing consumers remain unbroken.
4. **Re-index Knowledge Graph**:
   ```bash
   codebase-memory-mcp cli index_repository --repo-path /home/g0pi/Projects/Jarvis-OS --name JARVIS-V0
   ```
