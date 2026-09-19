"""
Notion Bridge & Autonomous Agent Fleet Subsystem for J.A.R.V.I.S. OS.
Enables full Notion API operations and dynamic Notion-hosted agent creation,
listing, execution, and bidirectional task synchronization.
"""

import os
import json
import time
import asyncio
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

from .logger import log_info, log_warn, log_error

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"


def get_notion_config() -> Tuple[str, str]:
    """Retrieve Notion API token and default database ID from environment or .env."""
    token = os.getenv("NOTION_TOKEN", "").strip().strip("\"'")
    db_id = os.getenv("NOTION_DATABASE_ID", "").strip().strip("\"'")

    if not token or not db_id:
        env_path = os.path.join(os.getcwd(), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("NOTION_TOKEN="):
                        val = line.split("=", 1)[1].strip().strip("\"'")
                        if not token:
                            token = val
                    elif line.startswith("NOTION_DATABASE_ID="):
                        val = line.split("=", 1)[1].strip().strip("\"'")
                        if not db_id:
                            db_id = val

    return token, db_id


# ══════════════════════════════════════════════════════════════════════════════
# Notion API Low-Level Client
# ══════════════════════════════════════════════════════════════════════════════

class NotionClient:
    """Zero-dependency HTTP client for the Notion REST API."""

    def __init__(self, token: Optional[str] = None, database_id: Optional[str] = None):
        cfg_token, cfg_db = get_notion_config()
        self.token = token or cfg_token
        self.default_database_id = database_id or cfg_db

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json",
        }

    def _request_sync(
        self,
        method: str,
        endpoint: str,
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 20.0,
    ) -> Dict[str, Any]:
        if not self.token:
            return {"success": False, "error": "NOTION_TOKEN is not configured."}

        url = f"{NOTION_BASE_URL}/{endpoint.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=self._headers())

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_data = resp.read().decode("utf-8")
                parsed = json.loads(resp_data) if resp_data else {}
                return {"success": True, "result": parsed}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            log_warn(f"Notion API HTTP error {e.code}: {err_body[:250]}", source="Notion")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("message", err_body[:200])
            except Exception:
                msg = err_body[:200]
            return {"success": False, "error": f"HTTP {e.code}: {msg}", "code": e.code}
        except Exception as ex:
            log_error(f"Notion API request exception: {ex}", source="Notion", exc=ex)
            return {"success": False, "error": str(ex)}

    async def _request(
        self,
        method: str,
        endpoint: str,
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 20.0,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(self._request_sync, method, endpoint, body, params, timeout)

    # ── Database Operations ───────────────────────────────────────────────────

    async def get_database(self, database_id: Optional[str] = None) -> Dict[str, Any]:
        target_db = database_id or self.default_database_id
        if not target_db:
            return {"success": False, "error": "database_id is required."}
        return await self._request("GET", f"databases/{target_db}")

    async def query_database(
        self,
        database_id: Optional[str] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        page_size: int = 25,
        start_cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        target_db = database_id or self.default_database_id
        if not target_db:
            return {"success": False, "error": "database_id is required."}

        body: Dict[str, Any] = {"page_size": min(page_size, 100)}
        if filter_dict:
            body["filter"] = filter_dict
        if sorts:
            body["sorts"] = sorts
        if start_cursor:
            body["start_cursor"] = start_cursor

        return await self._request("POST", f"databases/{target_db}/query", body=body)

    # ── Page Operations ───────────────────────────────────────────────────────

    async def create_page(
        self,
        parent: Dict[str, Any],
        properties: Dict[str, Any],
        children: Optional[List[Dict[str, Any]]] = None,
        icon: Optional[Dict[str, Any]] = None,
        cover: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"parent": parent, "properties": properties}
        if children:
            body["children"] = children
        if icon:
            body["icon"] = icon
        if cover:
            body["cover"] = cover
        return await self._request("POST", "pages", body=body)

    async def get_page(self, page_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"pages/{page_id}")

    async def update_page(
        self,
        page_id: str,
        properties: Optional[Dict[str, Any]] = None,
        archived: Optional[bool] = None,
        icon: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if properties is not None:
            body["properties"] = properties
        if archived is not None:
            body["archived"] = archived
        if icon is not None:
            body["icon"] = icon
        return await self._request("PATCH", f"pages/{page_id}", body=body)

    # ── Block Operations ──────────────────────────────────────────────────────

    async def get_block_children(self, block_id: str, page_size: int = 100) -> Dict[str, Any]:
        return await self._request("GET", f"blocks/{block_id}/children", params={"page_size": page_size})

    async def append_block_children(self, block_id: str, children: List[Dict[str, Any]]) -> Dict[str, Any]:
        return await self._request("PATCH", f"blocks/{block_id}/children", body={"children": children})

    # ── Workspace Search ──────────────────────────────────────────────────────

    async def search(
        self,
        query: str = "",
        filter_type: Optional[str] = None,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"query": query, "page_size": min(page_size, 100)}
        if filter_type in ["page", "database"]:
            body["filter"] = {"value": filter_type, "property": "object"}
        return await self._request("POST", "search", body=body)


# ══════════════════════════════════════════════════════════════════════════════
# Helper Functions: Block Formatting & Extraction
# ══════════════════════════════════════════════════════════════════════════════

def create_title_property(title_text: str) -> Dict[str, Any]:
    """Format a title property object for Notion pages."""
    return {"title": [{"type": "text", "text": {"content": title_text[:2000]}}]}


def create_rich_text_property(text: str) -> Dict[str, Any]:
    """Format a rich_text property object."""
    return {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}


def create_select_property(name: str) -> Dict[str, Any]:
    """Format a select property object."""
    return {"select": {"name": name}}


def text_to_notion_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    """Convert a markdown or plain text string into structured Notion block objects."""
    blocks: List[Dict[str, Any]] = []
    lines = markdown_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        trimmed = line.strip()

        if not trimmed:
            i += 1
            continue

        # Headings
        if trimmed.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": trimmed[4:][:2000]}}]}
            })
        elif trimmed.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": trimmed[3:][:2000]}}]}
            })
        elif trimmed.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": trimmed[2:][:2000]}}]}
            })
        # Bulleted list items
        elif trimmed.startswith("- ") or trimmed.startswith("* "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": trimmed[2:][:2000]}}]}
            })
        # Numbered list items
        elif len(trimmed) > 2 and trimmed[0].isdigit() and trimmed[1:3] in [". ", ") "]:
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": trimmed[3:][:2000]}}]}
            })
        # Callouts / quotes
        elif trimmed.startswith("> "):
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"type": "text", "text": {"content": trimmed[2:][:2000]}}],
                    "icon": {"type": "emoji", "emoji": "💡"}
                }
            })
        # Code blocks
        elif trimmed.startswith("```"):
            lang = trimmed[3:].strip() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_content = "\n".join(code_lines)[:2000]
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "language": lang if lang in ["python", "javascript", "typescript", "bash", "json", "html", "css", "rust", "cpp"] else "plain text",
                    "rich_text": [{"type": "text", "text": {"content": code_content}}]
                }
            })
        else:
            # Paragraph chunking (Notion limit is 2000 chars per text block)
            chunk = trimmed[:2000]
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}
            })

        i += 1

    # Notion API allows max 100 children per append call
    return blocks[:100]


def extract_plain_text_from_blocks(blocks: List[Dict[str, Any]]) -> str:
    """Convert Notion block children into a readable Markdown string."""
    text_chunks = []
    for b in blocks:
        b_type = b.get("type", "")
        data = b.get(b_type, {})
        rich_texts = data.get("rich_text", [])
        content = "".join(t.get("plain_text", "") for t in rich_texts)

        if b_type == "heading_1":
            text_chunks.append(f"# {content}")
        elif b_type == "heading_2":
            text_chunks.append(f"## {content}")
        elif b_type == "heading_3":
            text_chunks.append(f"### {content}")
        elif b_type == "bulleted_list_item":
            text_chunks.append(f"• {content}")
        elif b_type == "numbered_list_item":
            text_chunks.append(f"1. {content}")
        elif b_type == "code":
            lang = data.get("language", "")
            text_chunks.append(f"```{lang}\n{content}\n```")
        elif b_type == "callout":
            text_chunks.append(f"> {content}")
        elif content:
            text_chunks.append(content)

    return "\n\n".join(text_chunks).strip()


# ══════════════════════════════════════════════════════════════════════════════
# Notion Agent Fleet Subsystem
# ══════════════════════════════════════════════════════════════════════════════

class NotionAgentManager:
    """
    Manages autonomous AI agents registered within the Notion database.
    Enables creating new agents, listing registered agents, and executing
    tasks through them with automated task log synchronization back to Notion.
    """

    def __init__(self, client: NotionClient):
        self.client = client

    async def create_agent(
        self,
        name: str,
        role: str,
        instructions: str,
        capabilities: Optional[List[str]] = None,
        icon_emoji: str = "🤖",
    ) -> Dict[str, Any]:
        """
        Create a new agent entry in the Notion database with its persona,
        system prompt instructions, and capabilities.
        """
        agent_name = name.strip()
        title_text = f"🤖 Agent: {agent_name}"
        caps = capabilities or ["general_reasoning", "code_analysis", "project_tasks"]

        # Body blocks defining the agent persona and specifications
        body_blocks: List[Dict[str, Any]] = [
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [
                        {"type": "text", "text": {"content": f"Role: {role}\nStatus: Active\nRegistered for J.A.R.V.I.S. OS"}}
                    ],
                    "icon": {"type": "emoji", "emoji": icon_emoji},
                }
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Core Instructions & Persona"}}]}
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": instructions[:2000]}}]}
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Capabilities"}}]}
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": ", ".join(caps)}}]}
            },
            {
                "object": "block",
                "type": "divider",
                "divider": {}
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Task Execution History"}}]}
            }
        ]

        parent = {"database_id": self.client.default_database_id}
        properties = {"Name": create_title_property(title_text)}
        icon = {"type": "emoji", "emoji": icon_emoji}

        res = await self.client.create_page(
            parent=parent,
            properties=properties,
            children=body_blocks,
            icon=icon
        )

        if not res.get("success"):
            return res

        page_data = res.get("result", {})
        page_id = page_data.get("id")
        page_url = page_data.get("url")

        log_info(f"Notion Agent '{agent_name}' created successfully (ID: {page_id})", source="Notion")
        return {
            "success": True,
            "agent": {
                "id": page_id,
                "name": agent_name,
                "role": role,
                "capabilities": caps,
                "url": page_url,
            },
            "message": f"Agent '{agent_name}' registered in Notion database."
        }

    async def list_agents(self) -> Dict[str, Any]:
        """List all agents registered in the Notion database."""
        # Query database for pages with title starting with "🤖 Agent:" or "[Agent]"
        query_res = await self.client.query_database()
        if not query_res.get("success"):
            return query_res

        results = query_res.get("result", {}).get("results", [])
        agents: List[Dict[str, Any]] = []

        for row in results:
            props = row.get("properties", {})
            title_text = ""
            for _, val in props.items():
                if val.get("type") == "title":
                    title_text = "".join(t.get("plain_text", "") for t in val.get("title", []))
                    break

            if "Agent:" in title_text or "[Agent]" in title_text:
                clean_name = title_text.replace("🤖 Agent:", "").replace("[Agent]", "").strip()
                page_id = row.get("id")
                page_url = row.get("url")
                agents.append({
                    "id": page_id,
                    "name": clean_name,
                    "title": title_text,
                    "url": page_url,
                    "created_time": row.get("created_time"),
                    "last_edited_time": row.get("last_edited_time"),
                })

        return {
            "success": True,
            "total_agents": len(agents),
            "agents": agents
        }

    async def get_agent_details(self, agent_name_or_id: str) -> Dict[str, Any]:
        """Fetch agent definition, role, and instructions from Notion."""
        target = agent_name_or_id.strip()
        page_id = None

        # Check if argument is already a page ID
        if len(target) in [32, 36] and ("-" in target or target.isalnum()):
            page_id = target
        else:
            # Look up by name
            agents_res = await self.list_agents()
            if not agents_res.get("success"):
                return agents_res

            for ag in agents_res.get("agents", []):
                if ag["name"].lower() == target.lower() or target.lower() in ag["name"].lower():
                    page_id = ag["id"]
                    break

        if not page_id:
            return {"success": False, "error": f"Agent '{agent_name_or_id}' not found in Notion."}

        # Fetch block children to read instructions
        blocks_res = await self.client.get_block_children(page_id)
        if not blocks_res.get("success"):
            return blocks_res

        blocks = blocks_res.get("result", {}).get("results", [])
        full_content = extract_plain_text_from_blocks(blocks)

        # Parse role from callout or content
        role = "Specialist Agent"
        instructions = full_content
        for b in blocks:
            if b.get("type") == "callout":
                callout_text = "".join(t.get("plain_text", "") for t in b.get("callout", {}).get("rich_text", []))
                for line in callout_text.splitlines():
                    if "role:" in line.lower():
                        role = line.split(":", 1)[1].strip()

        return {
            "success": True,
            "agent": {
                "id": page_id,
                "name": agent_name_or_id,
                "role": role,
                "instructions": instructions,
            }
        }

    async def call_agent(
        self,
        agent_name_or_id: str,
        task: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a task using a specified Notion agent's instructions,
        and synchronize execution details and output back into Notion.
        """
        ag_details = await self.get_agent_details(agent_name_or_id)
        if not ag_details.get("success"):
            return ag_details

        agent_info = ag_details["agent"]
        agent_name = agent_info["name"]
        agent_role = agent_info["role"]
        agent_instructions = agent_info["instructions"]
        page_id = agent_info["id"]

        log_info(f"Invoking Notion Agent '{agent_name}' for task: {task[:60]}...", source="Notion")

        # Build prompt using agent's system instructions
        system_prompt = (
            f"You are {agent_name}, a specialized autonomous AI agent operating within J.A.R.V.I.S. OS.\n"
            f"Role: {agent_role}\n\n"
            f"=== AGENT INSTRUCTIONS FROM NOTION ===\n"
            f"{agent_instructions}\n\n"
            f"Execute the requested task thoroughly, precisely, and with maximum quality."
        )

        user_content = task
        if context:
            user_content += f"\n\nContext:\n{context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        # Execute through Jarvis LLM Provider Manager with resilient fallback
        output_text = ""
        try:
            from .providers import llm_manager
            llm_res = await llm_manager.chat_completion(
                messages=messages,
                temperature=0.4,
                max_tokens=2500
            )
            if isinstance(llm_res, dict):
                if "choices" in llm_res and len(llm_res["choices"]) > 0:
                    output_text = llm_res["choices"][0].get("message", {}).get("content", "")
                elif "candidates" in llm_res and len(llm_res["candidates"]) > 0:
                    parts = llm_res["candidates"][0].get("content", {}).get("parts", [])
                    output_text = "".join(p.get("text", "") for p in parts)
                elif "text" in llm_res:
                    output_text = llm_res["text"]
                elif "content" in llm_res:
                    output_text = llm_res["content"]
            elif isinstance(llm_res, str):
                output_text = llm_res
        except Exception as ex:
            log_warn(f"LLM Manager unavailable ({ex}), falling back to direct provider...", source="Notion")

        if not output_text:
            # Zero-dependency fallback using Gemini API with urllib
            gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not gemini_key:
                env_path = os.path.join(os.getcwd(), ".env")
                if os.path.exists(env_path):
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("GEMINI_API_KEY="):
                                gemini_key = line.split("=", 1)[1].strip().strip("\"'")
                                break
            if gemini_key:
                def _gemini_call():
                    try:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                        payload = {
                            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
                            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048},
                            "systemInstruction": {"parts": [{"text": system_prompt}]}
                        }
                        data = json.dumps(payload).encode("utf-8")
                        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
                        with urllib.request.urlopen(req, timeout=30.0) as resp:
                            data_resp = json.loads(resp.read().decode("utf-8"))
                            cands = data_resp.get("candidates", [])
                            if cands:
                                parts = cands[0].get("content", {}).get("parts", [])
                                return "".join(p.get("text", "") for p in parts)
                    except Exception as e:
                        log_error(f"Fallback Gemini call failed: {e}", source="Notion")
                    return ""
                output_text = await asyncio.to_thread(_gemini_call)

        if not output_text:
            return {"success": False, "error": "Failed to generate LLM response for Notion agent."}

        # Synchronize task execution log back to Notion page
        sync_success = False
        try:
            timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
            log_blocks: List[Dict[str, Any]] = [
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": [{"type": "text", "text": {"content": f"📋 Task Run: {task[:60]} ({timestamp_str})"[:2000]}}]}
                },
                {
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": [{"type": "text", "text": {"content": f"Status: Completed\nTimestamp: {timestamp_str}\nPrompt: {task[:500]}"[:2000]}}],
                        "icon": {"type": "emoji", "emoji": "✅"}
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": output_text[:2000]}}]}
                },
                {
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                }
            ]
            append_res = await self.client.append_block_children(page_id, log_blocks)
            sync_success = append_res.get("success", False)
        except Exception as sync_ex:
            log_warn(f"Failed to append task log to Notion page {page_id}: {sync_ex}", source="Notion")

        card_data = {
            "agentName": agent_name,
            "role": agent_role,
            "task": task,
            "output": output_text,
            "pageId": page_id,
            "synced": sync_success,
        }

        return {
            "success": True,
            "agent": agent_name,
            "role": agent_role,
            "task": task,
            "output": output_text,
            "page_id": page_id,
            "notion_synced": sync_success,
            "displayCard": {
                "type": "notion_agent_response",
                "title": f"Notion Agent ⟶ {agent_name}",
                "data": card_data
            }
        }


# ══════════════════════════════════════════════════════════════════════════════
# Singleton Instances & Unified Dispatch Router
#══════════════════════════════════════════════════════════════════════════════

notion_client = NotionClient()
notion_agent_manager = NotionAgentManager(notion_client)


async def dispatch_notion_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Unified dispatcher for all Notion tools invoked by Jarvis or agents."""
    t = tool_name.lower()

    # 1. Database & Page Operations
    if t in ["notion_query_database", "notion_query"]:
        db_id = args.get("database_id")
        filter_dict = args.get("filter")
        sorts = args.get("sorts")
        page_size = int(args.get("page_size", 20))
        res = await notion_client.query_database(db_id, filter_dict, sorts, page_size)
        if res.get("success"):
            results = res.get("result", {}).get("results", [])
            items = []
            for r in results:
                props = r.get("properties", {})
                title = ""
                for _, v in props.items():
                    if v.get("type") == "title":
                        title = "".join(x.get("plain_text", "") for x in v.get("title", []))
                        break
                items.append({"id": r.get("id"), "title": title, "url": r.get("url")})
            return {
                "success": True,
                "count": len(items),
                "items": items,
                "raw": res.get("result"),
                "displayCard": {
                    "type": "notion_response",
                    "title": "Notion Database Query",
                    "data": {"action": "query", "items": items, "count": len(items)}
                }
            }
        return res

    elif t in ["notion_create_page", "notion_create_database_item"]:
        title = args.get("title", "Untitled Page")
        content = args.get("content", "")
        db_id = args.get("database_id") or notion_client.default_database_id
        parent = {"database_id": db_id}
        properties = {"Name": create_title_property(title)}
        children = text_to_notion_blocks(content) if content else None

        res = await notion_client.create_page(parent=parent, properties=properties, children=children)
        if res.get("success"):
            page_data = res.get("result", {})
            return {
                "success": True,
                "page_id": page_data.get("id"),
                "url": page_data.get("url"),
                "title": title,
                "displayCard": {
                    "type": "notion_response",
                    "title": f"Created Notion Page: {title}",
                    "data": {"action": "create_page", "title": title, "url": page_data.get("url"), "page_id": page_data.get("id")}
                }
            }
        return res

    elif t in ["notion_get_page", "notion_read_page"]:
        page_id = args.get("page_id", "")
        if not page_id:
            return {"success": False, "error": "page_id is required."}
        return await notion_client.get_page(page_id)

    elif t in ["notion_get_page_content", "notion_get_blocks"]:
        page_id = args.get("page_id", "")
        if not page_id:
            return {"success": False, "error": "page_id is required."}
        res = await notion_client.get_block_children(page_id)
        if res.get("success"):
            blocks = res.get("result", {}).get("results", [])
            text = extract_plain_text_from_blocks(blocks)
            return {"success": True, "page_id": page_id, "text": text, "blocks_count": len(blocks)}
        return res

    elif t in ["notion_append_blocks", "notion_write_content"]:
        page_id = args.get("page_id", "")
        content = args.get("content", "")
        if not page_id or not content:
            return {"success": False, "error": "page_id and content are required."}
        blocks = text_to_notion_blocks(content)
        return await notion_client.append_block_children(page_id, blocks)

    elif t in ["notion_update_page"]:
        page_id = args.get("page_id", "")
        archived = args.get("archived")
        title = args.get("title")
        props = {"Name": create_title_property(title)} if title else None
        return await notion_client.update_page(page_id, properties=props, archived=archived)

    elif t in ["notion_search"]:
        query = args.get("query", "")
        filter_type = args.get("filter_type")
        res = await notion_client.search(query=query, filter_type=filter_type)
        if res.get("success"):
            raw_results = res.get("result", {}).get("results", [])
            items = []
            for r in raw_results:
                obj_type = r.get("object")
                title = ""
                if obj_type == "page":
                    props = r.get("properties", {})
                    for _, v in props.items():
                        if v.get("type") == "title":
                            title = "".join(x.get("plain_text", "") for x in v.get("title", []))
                            break
                elif obj_type == "database":
                    title = "".join(x.get("plain_text", "") for x in r.get("title", []))
                items.append({"id": r.get("id"), "type": obj_type, "title": title or "Untitled", "url": r.get("url")})
            return {
                "success": True,
                "count": len(items),
                "items": items,
                "displayCard": {
                    "type": "notion_response",
                    "title": f"Notion Search: '{query}'",
                    "data": {"action": "search", "query": query, "items": items, "count": len(items)}
                }
            }
        return res

    # 2. Notion Agent Fleet Operations
    elif t in ["notion_create_agent", "create_notion_agent"]:
        name = args.get("name") or args.get("agent_name", "")
        role = args.get("role", "Specialist Autonomous Agent")
        instructions = args.get("instructions") or args.get("prompt") or ""
        capabilities = args.get("capabilities", [])
        if not name or not instructions:
            return {"success": False, "error": "name and instructions are required to create a Notion Agent."}
        return await notion_agent_manager.create_agent(name, role, instructions, capabilities)

    elif t in ["notion_list_agents", "list_notion_agents"]:
        return await notion_agent_manager.list_agents()

    elif t in ["notion_call_agent", "call_notion_agent", "delegate_to_notion_agent"]:
        agent = args.get("agent_name") or args.get("agent") or args.get("name") or ""
        task = args.get("task") or args.get("prompt") or ""
        context = args.get("context")
        if not agent or not task:
            return {"success": False, "error": "agent_name and task are required to call a Notion Agent."}
        return await notion_agent_manager.call_agent(agent, task, context)

    return {"success": False, "error": f"Unknown Notion tool: {tool_name}"}
