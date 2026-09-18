"""
Friday-OS — Telegram LLM Provider Integration
Exposes Omniroute, Gemini, and Groq providers for Friday Telegram Channel.
"""

try:
    from brain.providers import (
        LLMProvider,
        OmnirouteProvider,
        GeminiProvider,
        GroqProvider,
        ProviderManager,
        llm_manager,
    )
except ImportError:
    from core_engine.providers import (
        LLMProvider,
        OmnirouteProvider,
        GeminiProvider,
        GroqProvider,
        ProviderManager,
        llm_manager,
    )

__all__ = [
    "LLMProvider",
    "OmnirouteProvider",
    "GeminiProvider",
    "GroqProvider",
    "ProviderManager",
    "llm_manager",
]
