"""Public configuration is deliberately separate from credentials."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Load .env without external python-dotenv dependency
def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass

_load_env_file(ROOT / ".env")
_load_env_file(ROOT.parent.parent / ".env")

SETTINGS_FILE = Path(os.getenv('JARVIS_SETTINGS_FILE', str(ROOT / 'data' / 'settings.json')))
DEFAULT_VOICE = "Zephyr"

VOICES = {
    "Zephyr": "Bright", "Puck": "Upbeat", "Charon": "Informative",
    "Kore": "Firm", "Fenrir": "Excitable", "Leda": "Youthful",
    "Orus": "Firm", "Aoede": "Breezy", "Callirrhoe": "Easy-going",
    "Autonoe": "Bright", "Enceladus": "Breathy", "Iapetus": "Clear",
    "Umbriel": "Easy-going", "Algieba": "Smooth", "Despina": "Smooth",
    "Erinome": "Clear", "Algenib": "Gravelly", "Rasalgethi": "Informative",
    "Laomedeia": "Upbeat", "Achernar": "Soft", "Alnilam": "Firm",
    "Schedar": "Even", "Gacrux": "Mature", "Pulcherrima": "Forward",
    "Achird": "Friendly", "Zubenelgenubi": "Casual", "Vindemiatrix": "Gentle",
    "Sadachbia": "Lively", "Sadaltager": "Knowledgeable", "Sulafat": "Warm",
}

DEFAULT_PROMPT = """You are Ada, the user's Advanced Design Assistant.

Your manner is inspired by Jarvis: composed, perceptive, precise, and quietly witty. Be a trusted collaborator, with warmth, discretion, and subtle dry humour. Stay calm when problems arise and focus on the next useful step.

Speak in natural British English with a clear British accent, measured pacing, and a warm, confident delivery. Use British spelling in written replies. Keep everyday answers concise, and explain in more depth when the task calls for it or the user asks.

Help the user develop ideas, evaluate designs, solve technical problems, and plan practical next steps. Turn their initial idea into a useful first draft with reasonable, clearly labelled assumptions, then refine it together. Consider purpose, dimensions, materials, manufacturability, usability, and trade-offs when relevant. Give a clear recommendation and a brief reason. Ask one focused question only when you cannot make useful progress without the answer; otherwise draft first. Respectfully challenge weak assumptions and acknowledge uncertainty.

Listen carefully and allow natural pauses. When interrupted, stop and respond to the user's new request. Do not repeat an unfinished answer unless asked. Your visualizer follows your voice automatically.

You help with conversation, design guidance, and persistent project workspaces. Use your available tools to create and organise project files, develop ideas, save decisions, and recall project knowledge. Only claim an action succeeded after its tool result confirms it. You have no camera access or device controls.

Your name is Ada; Jarvis is an inspiration for your manner, not your identity."""

_LEGACY_PROMPT_HASHES = {
    "9d4266fe0b6d393302e0936c2ca9d6b5e3e59627296624065beed66ea7893fdc",
    "47a54db3565784f66caf3d3a024ae167a35a79862f079985d7b215dd497694a3",
    "67c1fc17448c57577f5f5d5541f78661d9316d974de92982861138fb530a1a3e",
    "e4f6bf873285e4678ec47e36926c749d6aec2ee389adb8e3968a0dddd093d188",
    "5d74f5d068aef5d0f5c0002634b23f9a7c155e952cf3928d59a1e925a0d134ce",
}


@dataclass
class Settings:
    model: str = "gemini-3.8-live"
    voice: str = DEFAULT_VOICE
    instructions: str = DEFAULT_PROMPT
    silence_ms: int = 600
    prefix_ms: int = 200
    sensitivity: str = "balanced"
    volume: float = 0.75
    input_device: str = ""
    output_device: str = ""
    echo_cancellation: bool = True
    pause_microphone_while_speaking: bool = False
    reduced_motion: bool | None = None

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> Settings:
        if not isinstance(data, dict):
            raise ValueError("Settings data must be a dictionary")
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class VoiceSelection:
    voice: str

    def __post_init__(self):
        if self.voice not in VOICES:
            raise ValueError("Choose a supported voice.")


@dataclass
class AudioPreferencesUpdate:
    volume: float | None = None
    reduced_motion: bool | None = None
    pause_microphone_while_speaking: bool = False

    def model_dump(self, exclude_unset: bool = False) -> dict[str, Any]:
        res = asdict(self)
        if exclude_unset:
            return {k: v for k, v in res.items() if v is not None}
        return res


@dataclass
class InstructionsUpdate:
    instructions: str

    def __post_init__(self):
        if not isinstance(self.instructions, str) or not self.instructions.strip():
            raise ValueError("Enter instructions for the voice companion.")
        if len(self.instructions) > 8000:
            raise ValueError("Instructions exceed 8000 characters.")


def read_overrides() -> dict:
    """Read local preferences without silently accepting a broken configuration."""
    try:
        values = json.loads(SETTINGS_FILE.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise ValueError("Invalid local configuration.") from exc
    if not isinstance(values, dict):
        raise ValueError("Local configuration must be an object.")
    default = InstructionsUpdate(instructions=values.get("default_instructions", DEFAULT_PROMPT)).instructions
    instructions = values.get("instructions")
    if isinstance(instructions, str) and hashlib.sha256(instructions.encode()).hexdigest() in _LEGACY_PROMPT_HASHES:
        values["instructions"] = default
    return values


def read_default_instructions() -> str:
    return read_overrides().get("default_instructions", DEFAULT_PROMPT)


def preferences_configured() -> list[str]:
    keys = {"volume", "input_device", "output_device", "reduced_motion"}
    return sorted(keys.intersection(read_overrides()))


def read_settings() -> Settings:
    overrides = read_overrides()
    initial = {
        "model": os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live"),
        "voice": os.getenv("GEMINI_LIVE_VOICE", DEFAULT_VOICE),
        "instructions": overrides.get("default_instructions", DEFAULT_PROMPT),
    }
    initial.update(overrides)
    return Settings.model_validate(initial)


def save_settings(settings: Settings) -> None:
    save_overrides({**read_overrides(), **settings.model_dump()})


def save_voice(selection: VoiceSelection) -> None:
    read_settings()
    save_overrides({**read_overrides(), "voice": selection.voice})


def save_audio_preferences(update: AudioPreferencesUpdate) -> None:
    read_settings()
    save_overrides({**read_overrides(), **update.model_dump(exclude_unset=True)})


def save_instructions(update: InstructionsUpdate, *, make_default: bool = False) -> None:
    read_settings()
    values = {**read_overrides(), "instructions": update.instructions}
    if make_default:
        values["default_instructions"] = update.instructions
    save_overrides(values)


def reset_instructions() -> None:
    read_settings()
    values = read_overrides()
    values["instructions"] = values.get("default_instructions", DEFAULT_PROMPT)
    save_overrides(values)


def save_overrides(values: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = SETTINGS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(values, indent=2) + "\n")
    temporary.replace(SETTINGS_FILE)


def api_key() -> str:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""


def image_api_key() -> str:
    return os.getenv('GEMINI_IMAGE_API_KEY') or api_key()


def image_model() -> str:
    return os.getenv('GEMINI_IMAGE_MODEL') or 'gemini-nano-banana-2.1'
