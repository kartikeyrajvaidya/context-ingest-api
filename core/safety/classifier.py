"""Cheap LLM safety classifier."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from configs.safety import SafetyConfig
from core.services.openai_client import get_openai_client
from core.services.prompts import SAFETY_CLASSIFIER_PROMPT


class SafetyVerdict(BaseModel):
    safe: bool
    category: Literal["safe", "refuse"]
    reason: str = Field(max_length=200)


async def classify_question(question: str) -> SafetyVerdict:
    client = get_openai_client()
    completion = await client.chat.completions.parse(
        model=SafetyConfig.LLM_MODEL,
        messages=[
            {"role": "system", "content": SAFETY_CLASSIFIER_PROMPT},
            {"role": "user", "content": question},
        ],
        response_format=SafetyVerdict,
        temperature=0,
    )
    return completion.choices[0].message.parsed
