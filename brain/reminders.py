"""
J.A.R.V.I.S. Temporal Engine — Smart Reminders & Scheduling System.
Provides persistent storage (memory/vault/reminders.json), natural language time parsing,
async background trigger scheduler, and real-time UI/Voice notifications.
"""

import os
import json
import time
import re
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from brain.logger import log_reminder, log_error, log_info


DEFAULT_REMINDERS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "memory",
    "vault",
    "reminders.json"
)


def _format_time_string(dt: datetime) -> str:
    """Formats a datetime into a clean, human-readable string (e.g. 'Today at 5:30 PM')."""
    now = datetime.now()
    time_part = dt.strftime("%I:%M %p").lstrip("0")
    if dt.date() == now.date():
        return f"Today at {time_part}"
    elif dt.date() == (now + timedelta(days=1)).date():
        return f"Tomorrow at {time_part}"
    else:
        return f"{dt.strftime('%b %d')} at {time_part}"


def parse_due_time(due_in_minutes: Optional[float] = None, due_time_string: Optional[str] = None) -> tuple[int, str]:
    """
    Parses minutes or natural language time strings into (due_at_epoch_ms, formatted_string).
    """
    now = datetime.now()
    target_dt: datetime = now + timedelta(minutes=10)  # default

    if due_in_minutes is not None and due_in_minutes > 0:
        target_dt = now + timedelta(minutes=float(due_in_minutes))
    elif due_time_string:
        s = due_time_string.strip().lower()

        # Check 'in X minutes / hours / seconds'
        m_mins = re.search(r'(?:in\s+)?(\d+(?:\.\d+)?)\s*(?:min|minute|m)', s)
        m_hrs = re.search(r'(?:in\s+)?(\d+(?:\.\d+)?)\s*(?:hour|hr|h)', s)
        m_secs = re.search(r'(?:in\s+)?(\d+(?:\.\d+)?)\s*(?:sec|second|s)', s)

        if m_mins:
            target_dt = now + timedelta(minutes=float(m_mins.group(1)))
        elif m_hrs:
            target_dt = now + timedelta(hours=float(m_hrs.group(1)))
        elif m_secs:
            target_dt = now + timedelta(seconds=float(m_secs.group(1)))
        elif "tomorrow morning" in s:
            target_dt = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        elif "tomorrow evening" in s:
            target_dt = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        elif "tonight" in s:
            target_dt = now.replace(hour=20, minute=0, second=0, microsecond=0)
            if target_dt <= now:
                target_dt += timedelta(days=1)
        else:
            # Check clock time: e.g. "at 5:30 PM", "5:30pm", "17:00", "5pm"
            m_time = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', s)
            if m_time:
                hr = int(m_time.group(1))
                mn = int(m_time.group(2)) if m_time.group(2) else 0
                meridiem = m_time.group(3)
                if meridiem == "pm" and hr < 12:
                    hr += 12
                elif meridiem == "am" and hr == 12:
                    hr = 0
                target_dt = now.replace(hour=hr, minute=mn, second=0, microsecond=0)
                if target_dt <= now:
                    target_dt += timedelta(days=1)
            else:
                target_dt = now + timedelta(minutes=10)

    due_at_ms = int(target_dt.timestamp() * 1000)
    due_str = _format_time_string(target_dt)
    return due_at_ms, due_str


class ReminderManager:
    """Thread-safe persistent reminder manager with JSON backing."""

    def __init__(self, file_path: str = DEFAULT_REMINDERS_PATH):
        self.file_path = file_path
        self._lock = asyncio.Lock()
        self._reminders: Dict[str, Dict[str, Any]] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        """Loads reminders from JSON file."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._reminders = {r["id"]: r for r in data if "id" in r}
                    elif isinstance(data, dict):
                        self._reminders = data
            except Exception as e:
                log_error(f"Failed to read reminders from {self.file_path}: {e}", source="Reminders")
                self._reminders = {}
        else:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            self._save_to_disk()

    def _save_to_disk(self):
        """Persists reminders atomically to disk."""
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            tmp_file = f"{self.file_path}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(list(self._reminders.values()), f, indent=2)
            os.replace(tmp_file, self.file_path)
        except Exception as e:
            log_error(f"Failed to save reminders: {e}", source="Reminders")

    def create_reminder(
        self,
        text: str,
        due_in_minutes: Optional[float] = None,
        due_time_string: Optional[str] = None,
        category: str = "general"
    ) -> Dict[str, Any]:
        """Creates a new scheduled reminder and persists it."""
        now_ms = int(time.time() * 1000)
        due_at_ms, due_date_str = parse_due_time(due_in_minutes, due_time_string)
        rem_id = f"rem-{int(time.time())}-{os.urandom(2).hex()}"

        reminder = {
            "id": rem_id,
            "text": text.strip(),
            "createdAt": now_ms,
            "dueAt": due_at_ms,
            "dueDateString": due_date_str,
            "completed": False,
            "notified": False,
            "category": category
        }
        self._reminders[rem_id] = reminder
        self._save_to_disk()
        log_reminder(f"Created reminder: '{text}' ({due_date_str})", action="SET")
        return reminder

    def list_reminders(self, include_completed: bool = False) -> List[Dict[str, Any]]:
        """Returns list of reminders sorted by due time."""
        rems = list(self._reminders.values())
        if not include_completed:
            rems = [r for r in rems if not r.get("completed", False)]
        return sorted(rems, key=lambda r: r.get("dueAt", 0))

    def get_reminder(self, reminder_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single reminder by ID."""
        return self._reminders.get(reminder_id)

    def complete_reminder(self, reminder_id: str) -> bool:
        """Marks a reminder as completed."""
        if reminder_id in self._reminders:
            self._reminders[reminder_id]["completed"] = True
            self._save_to_disk()
            log_reminder(f"Completed reminder: '{self._reminders[reminder_id]['text']}'", action="DONE")
            return True
        return False

    def delete_reminder(self, reminder_id: str) -> bool:
        """Deletes a reminder permanently."""
        if reminder_id in self._reminders:
            text = self._reminders[reminder_id].get("text", "")
            del self._reminders[reminder_id]
            self._save_to_disk()
            log_reminder(f"Deleted reminder: '{text}'", action="DONE")
            return True
        return False

    def clear_completed(self) -> int:
        """Removes all completed reminders."""
        initial_len = len(self._reminders)
        self._reminders = {k: r for k, r in self._reminders.items() if not r.get("completed", False)}
        removed = initial_len - len(self._reminders)
        if removed > 0:
            self._save_to_disk()
        return removed

    def check_due_reminders(self) -> List[Dict[str, Any]]:
        """
        Scans for reminders whose due time has arrived, marks them notified, and returns them.
        """
        now_ms = int(time.time() * 1000)
        due = []
        changed = False

        for r in self._reminders.values():
            if not r.get("completed", False) and not r.get("notified", False):
                if r.get("dueAt", 0) <= now_ms:
                    r["notified"] = True
                    due.append(r)
                    changed = True

        if changed:
            self._save_to_disk()

        return due

    def get_display_card(self, action: str, data: Any) -> Dict[str, Any]:
        """Formats a UI SkillDisplayCard matching SkillDisplayCard.tsx."""
        if action == "reminder_created":
            return {
                "type": "reminder_created",
                "title": "Smart Reminder Set",
                "data": data
            }
        else:
            return {
                "type": "reminders_list",
                "title": "Active Reminders",
                "data": {"reminders": data}
            }


# Singleton instance
reminder_manager = ReminderManager()


async def run_reminder_scheduler(
    broadcast_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
    voice_notify_fn: Optional[Callable[[str], Any]] = None
):
    """
    Background daemon loop that evaluates due reminders every 2 seconds
    and triggers instant UI WebSocket chimes and proactive voice alerts.
    """
    log_info("Temporal Reminder Scheduler active (2s loop).", source="Reminders")
    last_day_checked = time.strftime("%Y-%m-%d")
    while True:
        try:
            # 0. Check for midnight day rollover to initialize new daily session and summarize prior days
            current_day = time.strftime("%Y-%m-%d")
            if current_day != last_day_checked:
                last_day_checked = current_day
                log_info(f"Midnight day rollover detected ({current_day}). Initializing new daily session...", source="Temporal")
                try:
                    from brain.memory import memory_engine
                    memory_engine.init_daily_session()
                except Exception as roll_err:
                    log_error(f"Failed to handle daily session rollover: {roll_err}", source="Temporal")

            due_items = reminder_manager.check_due_reminders()
            for item in due_items:
                log_reminder(f"🔔 DUE NOW: '{item['text']}' (Scheduled for {item['dueDateString']})", action="ALERT")

                # 1. Broadcast to React Web UI (triggers live audio chime & drawer alert)
                if broadcast_fn:
                    try:
                        await broadcast_fn({
                            "type": "reminder_due",
                            "reminder": item,
                            "displayCard": reminder_manager.get_display_card("reminder_created", item)
                        })
                    except Exception as b_err:
                        log_error(f"Failed to broadcast reminder: {b_err}", source="Reminders")

                # 2. Proactively alert operator through Jarvis voice session
                if voice_notify_fn:
                    try:
                        notification_prompt = (
                            f"[SYSTEM NOTIFICATION: REMINDER DUE NOW]\n"
                            f"Reminder: \"{item['text']}\"\n"
                            f"Scheduled Time: {item['dueDateString']}\n\n"
                            f"OPERATIONAL DIRECTIVE FOR JARVIS:\n"
                            f"- Politely and smoothly alert operator Gopi that this reminder is due right now in 1 articulate, natural sentence in your signature Jarvis voice."
                        )
                        await voice_notify_fn(notification_prompt)
                    except Exception as v_err:
                        log_error(f"Failed to deliver voice reminder prompt: {v_err}", source="Reminders")

        except asyncio.CancelledError:
            break
        except Exception as e:
            log_error(f"Scheduler loop error: {e}", source="Reminders")

        await asyncio.sleep(2.0)
