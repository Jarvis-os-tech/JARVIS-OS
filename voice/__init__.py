"""The Voice Layer — sovereign voice foundation for JARVIS OS.

Unified package providing real-time audio capture, PipeWire AEC, Silero VAD,
bounded playback with generation fences, offline wake-word standby, and
full-duplex Gemini Live conversation sessions.
"""
from .daemon import LiveVoice, live_config
from .decision_router import DecisionRouter, DecisionResult
from .echo import EchoCancellation, MonitorEchoCancellation, monitor_properties
from .speech import SpeechTurnGate, SileroSpeechDetector, SpokenInterruption, GateFrame
from .playback import Playback, MicrophoneBacklogError, PlaybackBacklogError
from .recovery import ConnectionRecovery, RecoveryDecision
from .standby import OpenWakeWordDetector, StandbyController, WakeWordUnavailable
from .ipc import ControlServer
from .fish_speaker import FishAudioClient, has_emotion_cues, strip_cues
from .config import Config, load as load_config, load_env
from .hypr_monitor import HyprlandMonitor, SessionContext
from . import daemon
from . import playback
from . import speech
from . import config
from . import echo
from . import decision_router
from . import hypr_monitor
from . import ipc
from . import recovery
from . import standby
from . import fish_speaker
from . import local_speech
from . import needle_router
from . import progress
from . import acknowledgements

def __getattr__(name: str):
    import importlib
    try:
        mod = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = mod
        return mod
    except ModuleNotFoundError as e:
        if e.name == f"{__name__}.{name}":
            raise AttributeError(f"module '{__name__}' has no attribute '{name}'") from e
        raise

__version__ = '0.1.0'

__all__ = [
    'LiveVoice',
    'live_config',
    'DecisionRouter',
    'DecisionResult',
    'EchoCancellation',
    'MonitorEchoCancellation',
    'monitor_properties',
    'SpeechTurnGate',
    'SileroSpeechDetector',
    'SpokenInterruption',
    'GateFrame',
    'Playback',
    'MicrophoneBacklogError',
    'PlaybackBacklogError',
    'ConnectionRecovery',
    'RecoveryDecision',
    'OpenWakeWordDetector',
    'StandbyController',
    'WakeWordUnavailable',
    'ControlServer',
    'FishAudioClient',
    'has_emotion_cues',
    'strip_cues',
    'Config',
    'load_config',
    'load_env',
    'HyprlandMonitor',
    'SessionContext',
]
