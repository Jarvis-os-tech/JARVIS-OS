# Universal Shared Memory for Jarvis OS: Leveraging Cognee & MCP

This report outlines how **Cognee** (`topoteretes/cognee`) can be integrated as the universal, shared memory and context engine across the entire **Jarvis OS** ecosystem—unifying local agents, cloud voice loops (Gemini Live Pro / Groq / Deepgram), local background processes, and browser-based workflows via the **Model Context Protocol (MCP)**.

---

## 1. Executive Summary & Architecture Vision

Jarvis OS is designed as a voice-first, multi-agent operating system on top of Omarchy (Arch/Hyprland/Quickshell). To achieve true agentic cohesion, Jarvis (CEO), Friday (Workflow & System Intelligence), OpenClaw/Ultron (Security & Permissions), and Hermes (Worker Layer) must share a **single, universal state and knowledge fabric** rather than operating in siloed context windows.

```
┌─────────────────────────────────────────────────────────────┐
│                       JARVIS OS HOST                        │
│                                                             │
│   ┌───────────────┐     ┌───────────────┐     ┌─────────┐   │
│   │  Jarvis (CEO) │     │ Friday (Intel)│     │ Hermes  │   │
│   └───────┬───────┘     └───────┬───────┘     └────┬────┘   │
│           │                     │                  │        │
│           └──────────┬──────────┴──────────────────┘        │
│                      ▼                                      │
│         [ Model Context Protocol (MCP) ]                    │
│                      │                                      │
│         ┌────────────┴────────────┐                         │
│         ▼                         ▼                         │
│  [ Cognee REST API ]      [ Local Standalone ]              │
│  (Central Graph Engine)   (Per-Session Cache)               │
│         │                         │                         │
│         └────────────┬────────────┘                         │
│                      ▼                                      │
│        [ Postgres + PGVector + Graph ]                      │
└─────────────────────────────────────────────────────────────┘
```

**Cognee** solves the core challenge of multi-agent persistence by providing:
1. **Automated Knowledge Graph Extraction:** Converts raw text, codebases, and voice interaction transcripts into structured entities, relations, and searchable vector chunks.
2. **Session Caching & Distillation (`remember` / `recall` / `improve`):** Fast session memory that automatically distills lessons, bug fixes, and user preferences into permanent graph knowledge.
3. **Native MCP Server Support:** Exposes standardized tools (`remember`, `recall`, `forget`, tool discovery) over `stdio`, `HTTP`, or `SSE`, allowing any MCP client (Claude Desktop, Cursor, custom Jarvis clients) to plug directly into the shared memory backend.

---

## 2. Core Capabilities of Cognee in Jarvis OS

### A. Universal Multi-Agent Sync
- **Shared State Across Roster:** When Jarvis or Friday makes an architectural decision or records user preferences (e.g., *“User prefers concise responses, bilingual English/Telgish”*), it is immediately committed via `cognee.remember()`.
- **Cross-Session Continuity:** When a background Hermes task or a new chat session starts, agents call `cognee.recall()` to fetch relevant historical context, eliminating repeated questions or lost instructions.

### B. Codebase & System Ingestion
- Jarvis OS manages system configs, Quickshell widgets, Python pipelines, and TypeScript extensions. Cognee can ingest entire repositories at once, mapping symbols, dependencies, and file structures into the knowledge graph so agents can reason over code relationships instantly.

### C. Browser & Extension Integration
- Using Cognee's browser connectors and MCP transport layers, browsing sessions, documentation lookups, and web artifacts are ingested directly into the user's dataset, bridging offline code memory with online research.

---

## 3. Recommended Implementation Plan for Jarvis OS

### Phase 1: Backend Deployment & Postgres Integration
1. **Containerized Deployment:** Run Cognee in API mode via Docker Compose (or natively with Postgres + PGVector backend) on `http://localhost:8000`.
2. **Environment Configuration:** Configure LLM and embedding providers (supporting user preference for cloud APIs like Gemini/Groq):
   ```bash
   LLM_PROVIDER=openai (or gemini/groq compatible endpoints)
   EMBEDDING_PROVIDER=openai
   VECTOR_DB_PROVIDER=pgvector
   ```

### Phase 2: MCP Server Integration
1. Start the Cognee MCP server in HTTP/SSE or stdio mode:
   ```bash
   uv run cognee-mcp --transport http --port 8001 --api-url http://localhost:8000
   ```
2. Register the MCP server in agent configurations (`~/.claude/settings.json`, client configs, or Hermes toolsets):
   ```json
   {
     "mcpServers": {
       "cognee-memory": {
         "url": "http://localhost:8001/mcp"
       }
     }
   }
   ```

### Phase 3: Agentic Hook Integration
- Configure session-end hooks across Jarvis, Friday, and Hermes to push session transcripts and learned rules into Cognee using `cognee.remember(..., session_id="...")`.
- Use `cognee.improve()` to curate session learnings into permanent project knowledge graphs.

---

## 4. Conclusion
Integrating Cognee transforms Jarvis OS from a collection of isolated agents into a unified cognitive architecture. By combining a self-hosted knowledge graph, PGVector, and standardized MCP endpoints, every component—from the voice-first duplex loop to background workers—shares a single, living memory.