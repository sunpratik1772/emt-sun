"""
Single seam for every LLM call in the codebase.

Import from this package only — never ``from google import genai`` elsewhere.

  * ``get_default_adapter()`` — process-wide ``GeminiAdapter`` singleton
  * ``gemini_configured()`` / ``gemini_api_key()`` — credential probes
  * ``probe_gemini_connection()`` — hello-world connectivity test

Swapping Gemini API keys for Vertex AI is a change in ``gemini_adapter.py`` only.
The frontend has no Gemini SDK or API calls.
"""
from .gemini_adapter import (
    GEMINI_API_KEY_2_ENV,
    GEMINI_API_KEY_3_ENV,
    GEMINI_API_KEY_ENVS,
    GEMINI_API_KEY_ENV,
    LLM_PROVIDER_ENV,
    VERTEX_LOCATION_ENV,
    VERTEX_PROJECT_ENV,
    GeminiAdapter,
    GeminiConnectivityResult,
    gemini_api_key,
    gemini_configured,
    get_default_adapter,
    llm_provider,
    probe_gemini_connection,
    reset_llm_runtime_for_tests,
)

__all__ = [
    "GEMINI_API_KEY_2_ENV",
    "GEMINI_API_KEY_3_ENV",
    "GEMINI_API_KEY_ENVS",
    "GEMINI_API_KEY_ENV",
    "LLM_PROVIDER_ENV",
    "VERTEX_LOCATION_ENV",
    "VERTEX_PROJECT_ENV",
    "GeminiAdapter",
    "GeminiConnectivityResult",
    "gemini_api_key",
    "gemini_configured",
    "get_default_adapter",
    "llm_provider",
    "probe_gemini_connection",
    "reset_llm_runtime_for_tests",
]
