"""Safety gate configuration for ContextIngest API."""

import os


def _bool(raw: str, default: bool) -> bool:
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class SafetyConfig:
    # Master switch. false → gate is a no-op; the main LLM sees every request.
    ENABLED = _bool(os.getenv("SAFETY_ENABLED", ""), True)

    # Cheap model used for the classifier call.
    LLM_MODEL = os.getenv("SAFETY_LLM_MODEL", "gpt-4o-mini")
