<!-- codebase-memory-mcp:start -->
# Codebase Memory

## Codebase Knowledge Graph (codebase-memory-mcp)

This project uses codebase-memory-mcp to maintain a knowledge graph of the codebase.
ALWAYS prefer MCP graph tools over grep/glob/file-search for code discovery.

### Priority Order
1. `search_graph` — find functions, classes, routes, variables by pattern
2. `trace_path` — trace who calls a function or what it calls
3. `get_code_snippet` — read specific function/class source code
4. `check_index_coverage` — validate candidate paths and missed ranges before claims
5. `query_graph` — run Cypher queries for complex patterns
6. `get_architecture` — high-level project summary

### Evidence tiers
- **Scout (Tier 1):** quick positive lookup with few calls and targeted source checks. Mark it provisional; do not make negative or exhaustive claims.
- **Verify (Tier 2, default):** task-directed graph evidence, relevant trace directions, exact snippets for material claims, and relevant pagination.
- **Auditor (Tier 3):** bounded-scope full verification with current generation, complete relevant pagination, both call directions and broader relationships when material, and every limitation disclosed.
- After candidate paths are known in any tier, call `check_index_coverage` once with every evidence path. Add relevant scopes for negative or exhaustive claims. A clean result means no recorded gap, not proof of completeness. For partial, skipped, excluded, stale, pending, or unknown coverage, read/grep the reported ranges or scope before relying on graph results.

### When to fall back to grep/glob
- Searching for string literals, error messages, config values
- Searching non-code files (Dockerfiles, shell scripts, configs)
- When MCP tools return insufficient results

### Examples
- Find a handler: `search_graph(name_pattern=".*OrderHandler.*")`
- Who calls it: `trace_path(function_name="OrderHandler", direction="inbound")`
- Read source: `get_code_snippet(qualified_name="pkg/orders.OrderHandler")`

### Session resets and subagents
- At session start or after compaction, confirm the nearest graph project and generation with `list_projects` or `index_status`, then choose Scout, Verify, or Auditor.
- Before spawning a subagent, query the graph and coverage in the parent. Pass the tier, project, generation/freshness, bounded scope, queries and pagination state, qualified symbols, paths, call-chain findings, coverage evidence with ranges/reasons, source fallback already performed, and unresolved questions in the delegated task context.
- Do not assume subagents inherit MCP access or the parent conversation. If a child lacks MCP tools, it must not call or claim MCP access. It should use the supplied evidence and read/grep exact source, especially every reported missed-coverage range.
<!-- codebase-memory-mcp:end -->

# 🛡️ JARVIS-OS — Workspace Rules (Ponytail Engineering Directive)

> **Scope**: Active across Antigravity CLI (`agy`), Antigravity 2.0 (GUI), and Antigravity IDE.  
> **Master Reference**: [`CODEBASE_REFERENCE.md`](file:///home/g0pi/Projects/Jarvis-OS/CODEBASE_REFERENCE.md)  
> **Knowledge Graph Project**: `JARVIS-V0`  

---

## ⚡ 1. The 4-Step Mandatory Engineering Cycle

1. **Gain Full Problem Clarity First**:
   - Understand the exact goal, the real problem, and what is NOT needed.
   - Ask: *Does this need to exist?* Skip speculative abstractions or unrequested features (YAGNI).
   - Trace the whole flow end-to-end through every affected file before editing.
   - Establish concrete acceptance criteria for verification.
2. **Reconnaissance via `codebase-memory-mcp`**:
   - Never write code before checking what is ALREADY implemented in JARVIS-OS.
   - Run `search_graph` and `trace_path` to find existing classes, helpers, and workers.
   - Re-implementing existing utilities is banned slop.
3. **Clean Root-Cause Implementation**:
   - Select the domain language from the Polyglot Matrix.
   - Climb the Ponytail Ladder: Reuse existing code $\rightarrow$ Stdlib $\rightarrow$ Native platform $\rightarrow$ Installed packages $\rightarrow$ Shortest working diff.
   - Patch the shared handler where all caller paths route through.
4. **Full Clarity Testing & Perfection Verification**:
   - Test against the Step 1 clarity criteria to ensure the feature is 100% complete and perfect.
   - Compile and verify: `npm run build:native` and `npm run lint`.
   - Trace callers with `trace_path` to guarantee zero regressions on sibling consumers.
   - Re-index knowledge graph: `codebase-memory-mcp cli index_repository --repo-path /home/g0pi/Projects/Jarvis-OS --name JARVIS-V0`.

---

## 🎯 2. Polyglot Language Hierarchy & Responsibilities

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

---

## 🛠️ 3. Verification & Knowledge Graph Updates

```bash
# Run system unified launcher:
python3 main.py --dry-run
# or identically:
npm run dev -- --dry-run

# Build native:
npm run build:native

# Lint & typecheck UI:
npm run lint

# Keep knowledge graph synchronized:
codebase-memory-mcp cli index_repository --repo-path /home/g0pi/Projects/Jarvis-OS --name JARVIS-V0
```
