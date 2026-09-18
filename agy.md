# Replace Prime Agent with Antigravity (AGY) Autonomous Coding Engine

This implementation plan details the complete transition in **JARVIS OS** from `prime-agent` to the **Antigravity CLI (`agy`)** as the primary, dedicated autonomous batch coding engine.

---

## Architecture Overview

```
                        ┌──────────────────────────────────────────────┐
                        │        USER (Voice / Telegram / Web UI)      │
                        └──────────────────────┬───────────────────────┘
                                               │
                                               ▼
                        ┌──────────────────────────────────────────────┐
                        │      J.A.R.V.I.S. Prime (Gemini Live)        │
                        │       Intent Routing & System Prompt         │
                        └──────────────────────┬───────────────────────┘
                                               │ Tool: delegate_to_agy
                                               ▼
                        ┌──────────────────────────────────────────────┐
                        │             server/skills.ts                 │
                        │   (delegate_to_agy + backward compat alias)  │
                        └──────────────────────┬───────────────────────┘
                                               │
                                               ▼
                        ┌──────────────────────────────────────────────┐
                        │             server/agyBridge.ts              │
                        │   (Replaces primeBridge.ts as primary)       │
                        └──────────────────────┬───────────────────────┘
                                               │
                                               ▼
                        ┌──────────────────────────────────────────────┐
                        │          Antigravity CLI (agy v1.2.6)        │
                        │                                              │
                        │   agy -p "<prompt>"                          │
                        │       --dangerously-skip-permissions         │
                        │       --output-format json                   │
                        │       --effort medium                        │
                        │       --add-dir <project_cwd>                │
                        └──────────────────────┬───────────────────────┘
                                               │
                                               ▼
                        ┌──────────────────────────────────────────────┐
                        │    Autonomous In-Project Execution Loop      │
                        │    • Inspect AST & codebase structure        │
                        │    • Write & modify code files               │
                        │    • Run tests & type checks (run_command)   │
                        │    • Self-heal on syntax/runtime errors      │
                        └──────────────────────┬───────────────────────┘
                                               │
                                               ▼
                        ┌──────────────────────────────────────────────┐
                        │       Structured Result & Telemetry          │
                        │  (Response, CodeBlocks, Duration, Tokens)    │
                        ├──────────────────────┬───────────────────────┤
                        │                      │                       │
                        ▼                      ▼                       ▼
               WebSocket Display Card      Telegram Bot          Audio Speech
                 (agy_response)              (/code)               Summary
```

---

## User Review Required

> [!IMPORTANT]
> **Complete Replacement with Safe Fallbacks**:
> `prime-agent` will be retired as the default coding provider in favor of `agy` (Antigravity CLI).
> To prevent breaking any existing external clients, saved bookmarks, or habits:
> 1. `delegate_to_prime_agent` will remain registered in `skills.ts` as an alias that maps directly to `delegate_to_agy`.
> 2. `primeBridge.ts` will re-export functions from `agyBridge.ts` so any background imports continue to work without runtime faults.
> 3. Legacy REST routes (`/api/prime/*`) will redirect to `/api/agy/*`.

> [!NOTE]
> **Sandboxing & Blast Radius**:
> Autonomous execution uses `--dangerously-skip-permissions` so the agent can inspect, write, and test without human interactive stalls. To keep execution safe, the bridge always pins `cwd` to the project root and explicitly supplies `--add-dir <workspace_path>`.

---

## Proposed Changes

Grouped logically by subsystem:

---

### 1. Bridge Layer (Core Execution Engine)

#### [NEW] [agyBridge.ts](file:///home/g0pi/Projects/Jarvis-OS/server/agyBridge.ts)
* Create the core bridge interfacing with `/home/g0pi/.local/bin/agy`:
  * `getAgyBin()`: Resolves binary path from `AGY_BIN`, `~/.local/bin/agy`, or system PATH.
  * `checkAgyHealth()`: Runs `agy --version` and inspects config readiness, returning `{ ok, installed, version, path, engine: "antigravity-cli" }`.
  * `extractCodeBlocks(markdown)`: Parses fenced code blocks with language and target filename.
  * `execAgyAgent(prompt, options)`:
    * Arguments: `prompt: string`, `options?: { timeout?: number; cwd?: string; effort?: "low" | "medium" | "high"; conversationId?: string }`.
    * Spawns child process: `agy -p "<prompt>" --dangerously-skip-permissions --output-format json [--effort <effort>] [--conversation <id>]`.
    * Parses structured JSON payload (`status`, `response`, `duration_seconds`, `num_turns`, `usage`, `conversation_id`).
    * Returns normalized `AgyResult` with formatted code snippets, execution duration, and speech summary.

#### [MODIFY] [primeBridge.ts](file:///home/g0pi/Projects/Jarvis-OS/server/primeBridge.ts)
* Update `primeBridge.ts` to act as a lightweight backward-compatibility wrapper pointing to `agyBridge.ts`, ensuring legacy scripts or imports do not break.

---

### 2. Registry & Skill Routing Layer

#### [MODIFY] [agents.registry.json](file:///home/g0pi/Projects/Jarvis-OS/agents.registry.json)
* Replace `"prime-agent"` with `"agy-agent"`:
  * `id`: `"agy-agent"`
  * `name`: `"Antigravity (AGY) Coding Engine"`
  * `role`: `"Primary Autonomous Software Engineer & Workspace Coding Agent"`
  * `description`: `"Dedicated autonomous coding engine powered by the Google Antigravity CLI (agy v1.2.6). Reads workspace context, modifies code files, runs tests/builds, and self-heals autonomously within the project."`
  * `platform`: `"antigravity-cli"`
  * `bridge`: `"server/agyBridge.ts"`
  * `status`: `"ready"`
  * `capabilities`: `["autonomous-coding", "workspace-editing", "test-verification", "batch-execution", "self-healing-code", "refactoring"]`

#### [MODIFY] [skills.ts](file:///home/g0pi/Projects/Jarvis-OS/server/skills.ts)
* Replace `primeAgentSkill` with `agyAgentSkill`:
  * Skill name: `delegate_to_agy`
  * Display name: `Antigravity (AGY Coding Agent)`
  * Description: Instructs Gemini that `delegate_to_agy` is the primary coding agent for all programming, debugging, refactoring, building, script writing, and test execution.
  * Keep `delegate_to_prime_agent` in `MODULAR_SKILLS` as an alias pointing to `agyAgentSkill`.
* In `delegate_task`:
  * Route coding and engineering tasks to `agy_agent` instead of `prime_agent`.

---

### 3. Server REST API & System Prompts

#### [MODIFY] [server.ts](file:///home/g0pi/Projects/Jarvis-OS/server/server.ts)
* Update imports: import `checkAgyHealth, execAgyAgent` from `./agyBridge.js`.
* Add REST routes:
  * `GET /api/agy/health` ⟶ Returns AGY installation, version, and auth status.
  * `POST /api/agy/chat` & `POST /api/agy/execute` ⟶ Invokes `execAgyAgent`.
  * Maintain `GET /api/prime/health` and `POST /api/prime/chat` as aliases forwarding to AGY.
* Update J.A.R.V.I.S. Core System Prompt:
  * Replace references to "Prime Agent" with "Antigravity (AGY) Agent".
  * Declare `delegate_to_agy` as the primary priority for all software engineering and product building.

---

### 4. Background Tasks & Telegram Bot

#### [MODIFY] [parallelTaskManager.ts](file:///home/g0pi/Projects/Jarvis-OS/server/parallelTaskManager.ts)
* Add `"agy_agent"` to `TaskCategory` (keep `"prime_agent"` as compatibility union).
* `generateVerbalAcknowledgment`: Announce *"Dispatching coding and software engineering task to Antigravity Agent."*
* `inferCategoryFromSkill`: Map `"agy"`, `"prime"`, and `"coding"` to `"agy_agent"`.

#### [MODIFY] [telegramBot.ts](file:///home/g0pi/Projects/Jarvis-OS/server/telegramBot.ts)
* Update `/code` command:
  * Announce: `⭐️ *Antigravity (AGY) Assigned*\n\nDispatched coding task:\n"${prompt}"\n\nBuilding and testing in background...`
  * Call `execAgyAgent(prompt)`.
  * Report: `✅ *Antigravity Completed*\n\n${r.text.slice(0, 3500)}` with code snippet counts and duration.

---

### 5. Web UI Cards & Telemetry

#### [MODIFY] [types.ts](file:///home/g0pi/Projects/Jarvis-OS/ui/web/src/types.ts)
* Add `'agy_response'` to `DisplayCardType`.
* Add `'agy_agent'` to `TaskCategory`.

#### [MODIFY] [SkillDisplayCard.tsx](file:///home/g0pi/Projects/Jarvis-OS/ui/web/src/components/SkillDisplayCard.tsx)
* Add rendering support for `agy_response` (displaying Antigravity branding, duration badge, token metrics, and extracted code blocks with copy buttons).
* Fall back cleanly for any legacy `prime_response` cards.

#### [MODIFY] [ParallelTaskDock.tsx](file:///home/g0pi/Projects/Jarvis-OS/ui/web/src/components/ParallelTaskDock.tsx)
* Handle `agy_agent` category with code/terminal icon and "Antigravity Agent" title.

#### [MODIFY] [verbalFeedback.ts](file:///home/g0pi/Projects/Jarvis-OS/ui/web/src/utils/verbalFeedback.ts)
* Add verbal acknowledgment phrases for `agy_agent`.

---

## Verification Plan

### Automated Verification
1. **Bridge Unit Test**:
   ```bash
   bun run -e 'import { checkAgyHealth, execAgyAgent } from "./server/agyBridge.ts";
     checkAgyHealth().then(h => console.log("Health:", h));
     execAgyAgent("Respond with exactly: BUILD_VERIFIED", { effort: "low" }).then(r => console.log("Exec:", r.success, r.text));'
   ```
   * Verify health reports `ok: true`, engine: `antigravity-cli`, version `1.2.6`.
   * Verify execution completes in batch mode with `success: true`.

2. **Server Compilation & Build Check**:
   ```bash
   bun run build
   ```
   * Ensure zero TypeScript or bundling errors.

3. **REST Endpoint Check**:
   ```bash
   curl -s http://localhost:18789/api/agy/health
   curl -s -X POST http://localhost:18789/api/agy/chat -H "Content-Type: application/json" -d '{"prompt":"Write a 2-line bash script"}'
   ```
   * Verify JSON response matches expected format.

### Manual Verification
1. **Voice / Intent Delegation**:
   * Issue a voice command: *"Jarvis, write a TypeScript helper function to format timestamps."*
   * Verify Jarvis acknowledges dispatching to Antigravity Agent.
   * Confirm the `agy_response` card renders on the web interface with syntax-highlighted code.
2. **Telegram Bot `/code`**:
   * Send `/code write a python script to check disk space` in Telegram.
   * Confirm prompt is acknowledged as Antigravity Agent and returns verified code output.
