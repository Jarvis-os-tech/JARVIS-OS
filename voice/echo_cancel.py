"""Compatibility shim redirecting audio.echo_cancel to voice_layer.echo."""
import sys
import voice.echo

sys.modules[__name__] = voice_layer.echo
from voice.echo import *
