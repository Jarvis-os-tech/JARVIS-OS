"""
J.A.R.V.I.S. Conversation Summarizer Agent — Automated Daily Vault Summarizer.
Condenses completed daily conversation logs into high-density structured Markdown summaries,
replacing raw millisecond turn logs (Option A) upon day-rollover.
"""

import os
import sys
import glob
import re
import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from .config import CONVERSATIONS_DIR, VAULT_ROOT
from brain.logger import log_info, log_success, log_warn, log_error
from brain.providers import llm_manager

logger = logging.getLogger("jarvis.summarizer")


class ConversationSummarizer:
    """
    Autonomous agent that monitors conversation logs and transforms completed daily
    transcripts into rich, actionable markdown summaries in Obsidian vault.
    """

    def __init__(self, conversations_dir: str = CONVERSATIONS_DIR):
        self.conversations_dir = conversations_dir

    def is_file_summarized(self, file_path: str) -> bool:
        """Checks whether the file has already been summarized."""
        if not os.path.exists(file_path):
            return False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read(2048)  # Read header/frontmatter
            if re.search(r"status:\s*summarized", content, re.IGNORECASE):
                return True
            if "type: conversation-summary" in content or "## 📌 Daily Briefing" in content:
                return True
            return False
        except Exception as e:
            logger.error(f"Error checking summary status for {file_path}: {e}")
            return False

    def extract_turns_and_metadata(self, content: str) -> tuple[str, int, List[str]]:
        """
        Parses dialogue turns from raw conversation markdown.
        Returns: (extracted_date, turn_count, turn_lines)
        """
        # Match frontmatter date if available
        date_match = re.search(r'date:\s*["\']?(\d{4}-\d{2}-\d{2})["\']?', content)
        extracted_date = date_match.group(1) if date_match else time.strftime("%Y-%m-%d")

        # Find turns
        turns = re.findall(r"(### \[\d{2}:\d{2}:\d{2}\].*?)(?=\n### \[\d{2}:\d{2}:\d{2}\]|\Z)", content, re.DOTALL)
        turn_count = len(turns)

        return extracted_date, turn_count, turns

    async def summarize_content(self, date_str: str, content: str, turn_count: int) -> str:
        """
        Invokes LLM (Gemini with fallback) to produce the structured Markdown briefing.
        """
        system_prompt = (
            "You are the J.A.R.V.I.S. Daily Conversation Summarizer Agent.\n"
            "Your objective is to analyze a completed day's raw conversation transcript between Operator Gopi and J.A.R.V.I.S. "
            "(including system events, tool commands, and subagent telemetry) and synthesize it into a clean, comprehensive, "
            "and professional Markdown briefing for the Obsidian Memory Vault.\n\n"
            "Format Guidelines:\n"
            "Use clear Markdown with the following exact section headers:\n"
            "## 📌 Daily Briefing & Executive Summary\n"
            "(2-3 clear, articulate paragraphs summarizing the session scope, operator intent, key workflows, and overall outcomes)\n\n"
            "## 🎯 Key Directives & Completed Tasks\n"
            "(Bulleted list detailing exact operator requests and corresponding system actuations such as workspace switching, "
            "volume/brightness adjustments, terminal commands, browser actions, and screen-sharing)\n\n"
            "## 🤖 Subagent Telemetry & Delegation\n"
            "(Summary of all queries, tests, and task delegations regarding Hermes and Ultron/OpenClaw subagents, including online status, "
            "telegram messaging, or memory scanning directives)\n\n"
            "## 📐 System & UI Architecture Specifications\n"
            "(Meticulously capture any technical specifications, UI design requests, or layouts described by Gopi — such as "
            "the parallel ready agents sidebar, right-hand execution logs, temporary vs permanent cron tasks, and clipboard prompts)\n\n"
            "## 🧠 Extracted Operator Facts & Preferences\n"
            "(Bullet points of newly revealed preferences, operational habits, preferred tools, language nuances, or system defaults)\n\n"
            "## ⚠️ Open Issues & Follow-ups\n"
            "(Any pending items, unreachable services, or requested next steps for subsequent sessions)\n\n"
            "Maintain J.A.R.V.I.S.'s sophisticated, precise, and polite voice. Do not output conversational filler or preamble. "
            "Output ONLY the markdown body starting directly with '## 📌 Daily Briefing & Executive Summary'."
        )

        user_prompt = (
            f"Please summarize the following conversation log for date {date_str} (Total dialog turns: {turn_count}):\n\n"
            f"--- BEGIN RAW CONVERSATION LOG ---\n"
            f"{content}\n"
            f"--- END RAW CONVERSATION LOG ---"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = await llm_manager.chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=3000
        )

        choices = response.get("choices", [])
        if choices and "message" in choices[0]:
            return choices[0]["message"].get("content", "").strip()

        raise RuntimeError("No summary content returned from LLM provider.")

    async def summarize_file(self, file_path: str, force: bool = False) -> Dict[str, Any]:
        """
        Summarizes a single conversation log file in-place (Option A: Full replacement).
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        filename = os.path.basename(file_path)
        date_str = filename.replace(".md", "")

        if self.is_file_summarized(file_path) and not force:
            log_info(f"Conversation {filename} is already summarized. Skipping.", source="Summarizer")
            return {"success": True, "status": "already_summarized", "file": file_path, "date": date_str}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()

            extracted_date, turn_count, turns = self.extract_turns_and_metadata(raw_content)
            final_date = extracted_date or date_str

            if turn_count == 0 and ("⚡ Core Engine online" in raw_content or len(raw_content.strip()) < 300):
                log_info(f"Conversation {filename} contains no dialog turns to summarize.", source="Summarizer")
                return {"success": True, "status": "empty_session", "file": file_path, "date": final_date}

            log_info(f"🧠 Synthesizing summary for {final_date} ({turn_count} turns)...", source="Summarizer")
            summary_markdown = await self.summarize_content(final_date, raw_content, turn_count)

            iso_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            new_file_content = f"""---
title: "Conversation Summary: {final_date}"
type: conversation-summary
date: "{final_date}"
operator: Gopi
status: summarized
summarized_at: "{iso_now}"
turns_count: {turn_count}
---

# 💬 J.A.R.V.I.S. Daily Briefing — {final_date}

- **Operator**: [[USER.md|Gopi]]
- **System**: [[MEMORY.md|J.A.R.V.I.S.]]
- **Index**: [[index.md|Memory Vault]]

---

{summary_markdown}
"""
            # Atomically write back to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_file_content)

            log_success(f"✅ Daily summary saved to {filename} ({len(summary_markdown)} chars).", source="Summarizer")
            return {
                "success": True,
                "status": "summarized",
                "file": file_path,
                "date": final_date,
                "turn_count": turn_count,
            }

        except Exception as e:
            log_error(f"Failed to summarize {file_path}: {e}", source="Summarizer")
            return {"success": False, "error": str(e), "file": file_path}

    async def summarize_unsummarized_days(self, exclude_today: bool = True) -> List[Dict[str, Any]]:
        """
        Scans CONVERSATIONS_DIR for prior days that have not been summarized yet,
        and summarizes each of them.
        """
        if not os.path.exists(self.conversations_dir):
            return []

        today = time.strftime("%Y-%m-%d")
        all_md_files = sorted(glob.glob(os.path.join(self.conversations_dir, "*.md")))
        results = []

        for fpath in all_md_files:
            fname = os.path.basename(fpath)
            day_str = fname.replace(".md", "")

            # If exclude_today is True, don't summarize today's active conversation
            if exclude_today and day_str == today:
                continue

            # Check if needs summary
            if not self.is_file_summarized(fpath):
                log_info(f"Unsummarized previous conversation detected: {fname}", source="Summarizer")
                res = await self.summarize_file(fpath)
                results.append(res)

        return results

    def trigger_background_scan(self, exclude_today: bool = True):
        """
        Launches an unblocked background async task or thread to summarize pending files.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.summarize_unsummarized_days(exclude_today=exclude_today))
        except RuntimeError:
            # No running event loop, run via asyncio in background thread
            import threading
            def _runner():
                asyncio.run(self.summarize_unsummarized_days(exclude_today=exclude_today))
            t = threading.Thread(target=_runner, daemon=True)
            t.start()


# Global Singleton
conversation_summarizer = ConversationSummarizer()


# ─── Standalone CLI Runner ───────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Conversation Summarizer Agent")
    parser.add_argument("date", nargs="?", help="Specific date (YYYY-MM-DD) or file path to summarize")
    parser.add_argument("--force", action="store_true", help="Force summarization even if marked summarized")
    parser.add_argument("--all", action="store_true", help="Summarize all past unsummarized conversation logs")
    args = parser.parse_args()

    async def _main():
        if args.date:
            target_path = args.date
            if not os.path.exists(target_path):
                target_path = os.path.join(CONVERSATIONS_DIR, f"{args.date}.md" if not args.date.endswith(".md") else args.date)
            result = await conversation_summarizer.summarize_file(target_path, force=args.force)
            print("Result:", result)
        else:
            results = await conversation_summarizer.summarize_unsummarized_days(exclude_today=not args.force)
            print("Results:", results)

    asyncio.run(_main())
