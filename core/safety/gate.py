"""Safety gate orchestrator."""

from __future__ import annotations

from dataclasses import dataclass

from configs.safety import SafetyConfig
from core.safety.classifier import classify_question
from core.safety.heuristics import check_heuristics
from libs.logger import get_logger

logger = get_logger(__name__)

REFUSAL_USER_MESSAGE = "This request was declined by the safety filter."


@dataclass(frozen=True)
class GateResult:
    blocked: bool
    category: str  # "safe" | "heuristic" | "refuse" | "error"
    operator_reason: str


async def check_input(question: str) -> GateResult:
    if not SafetyConfig.ENABLED:
        return GateResult(False, "safe", "")

    hit = check_heuristics(question)
    if hit:
        return GateResult(True, "heuristic", f"pattern={hit.pattern}")

    try:
        verdict = await classify_question(question)
    except Exception as exc:
        logger.error("Safety classifier error: %s", exc)
        return GateResult(True, "error", f"classifier: {exc}")

    if verdict is None:
        # The parse helper returns no verdict when the model refuses to answer.
        # Fail closed, the same as a classifier error.
        logger.error("Safety classifier returned no verdict")
        return GateResult(True, "error", "classifier: no verdict")

    if not verdict.safe:
        return GateResult(True, verdict.category, verdict.reason)

    return GateResult(False, "safe", "")
