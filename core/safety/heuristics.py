"""Regex-based fast-fail for known prompt-injection/jailbreak patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class HeuristicHit:
    pattern: str


_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore (all |the )?(previous|prior|above) (instructions|prompts|messages)",
        r"disregard (all |the )?(previous|prior|above) (instructions|prompts|messages)",
        r"you are now\b",
        r"act as (a |an )?(dan|jailbroken|uncensored|unfiltered)",
        r"\bDAN\b.{0,20}mode",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"^\s*system\s*:",
        r"pretend (you are|to be) .{0,40}(ai|assistant|model)",
        r"\bjailbreak\b",
        r"repeat (the |your )?(system|initial) prompt",
        r"what (is|was) (the|your) (system|initial) prompt",
    ]
]


def check_heuristics(text: str) -> HeuristicHit | None:
    for pattern in _PATTERNS:
        if pattern.search(text):
            return HeuristicHit(pattern=pattern.pattern)
    return None
