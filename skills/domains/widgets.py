"""Declarative view adapters; all system effects stay in existing JARVIS tools."""
import asyncio
import json
import re
import subprocess

from skills.errors import SkillError
from ui.jarvis_widgets import backend
from ui.jarvis_widgets.view_schema import describe

ADAPTERS = {
    "widgets.show": "_adapter_show_widget",
    "widgets.canvas": "_adapter_manage_canvas",
    "widgets.manage": "_adapter_manage_widget",
    "widgets.schema": "_adapter_widget_schema",
    "widgets.apps": "_adapter_manage_app_stage",
}
ADAPTER_COMMANDS = {name: ("omarchy-shell",) for name in ADAPTERS}


class WidgetsDomain:
    async def _adapter_widget_schema(self):
        return describe()

    async def _adapter_manage_app_stage(self, action, query="", app_id="", address=""):
        if action == "applications" and len(query) <= 160:
            payload = {"action": action, "query": query}
        elif action == "windows":
            payload = {"action": action}
        elif action == "launch" and 0 < len(app_id) <= 160:
            payload = {"action": action, "id": app_id}
        elif action in ("focus", "park", "restore") and re.fullmatch(r"0x[0-9a-fA-F]{1,30}", address):
            payload = {"action": action, "address": address}
        else:
            raise SkillError("Choose an app stage action and supply its target")
        try:
            return await asyncio.to_thread(backend.shell_call, "desktop", payload)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise SkillError(str(error)) from error

    async def _adapter_show_widget(self, kind, title, data_json, widget_id="", presentation="floating", expires_seconds=120, revision=0, reopen=False):
        def present():
            widget = backend.make_widget(kind, title, json.loads(data_json), widget_id=widget_id,
                                         presentation=presentation, expires_seconds=expires_seconds, revision=revision, reopen=reopen)
            return backend.shell_call("present", widget)
        try:
            return await asyncio.to_thread(present)
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise SkillError(str(error)) from error

    async def _adapter_manage_canvas(self, action):
        methods = {
            "open": "open", "close": "close", "input": "input", "clear": "clear",
            "clear_all": "clearAll", "status": "status", "system": "showSystem",
            "audio": "showAudio", "media": "showMedia", "devices": "showDevices",
        }
        if action not in methods:
            raise SkillError("Unsupported canvas action")
        try:
            return await asyncio.to_thread(backend.shell_call, methods[action])
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise SkillError(str(error)) from error

    async def _adapter_manage_widget(self, action, widget_id="", x=None, y=None, index=None, dismiss=True):
        if action in ("clear", "clear_all", "status"):
            return await self._adapter_manage_canvas(action)
        if action not in ("dismiss", "pin", "unpin", "focus", "float", "canvas", "move", "state", "select"):
            raise SkillError("Unsupported widget action")
        try:
            payload = {"id": widget_id, "action": action}
            if action == "move":
                if type(x) is not int or type(y) is not int or not 0 <= x <= 100 or not 0 <= y <= 100:
                    raise SkillError("Move needs integer x and y percentages between 0 and 100")
                payload.update(x=x / 100, y=y / 100)
            elif action == "select":
                if type(index) is not int or not 1 <= index <= 9:
                    raise SkillError("Select needs an integer choice index between 1 and 9")
                if type(dismiss) is not bool:
                    raise SkillError("dismiss must be true or false")
                payload.update(index=index, dismiss=dismiss)
            return await asyncio.to_thread(backend.shell_call, "manage", payload)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise SkillError(str(error)) from error
