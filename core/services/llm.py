"""Answer-composition LLM service.

One call, one responsibility: take a question + conversation history +
retrieved chunks and return an `LLMAnswer` via OpenAI's structured-output
API. Prompt construction lives in `prompts.py`; client construction lives
in `openai_client.py`.
"""

from configs.llm import LLMConfig
from core.schema.llm_answer import LLMAnswer
from core.schema.retrieval_result import RetrievedChunk
from core.services.openai_client import get_openai_client
from core.services.prompts import build_answer_system_prompt
from core.services.prompts import build_answer_user_prompt
from libs.logger import get_logger

logger = get_logger(__name__)


class LLMParseError(Exception):
    """Non-fatal LLM failure: structured output did not parse.

    Caught by the action and mapped to the no-answer response path with
    status='llm_failed'.
    """


async def generate_answer(
    question: str,
    conversation_turns: list[dict],
    retrieved_chunks: list[RetrievedChunk],
) -> LLMAnswer:
    """Compose a grounded answer using the answer model.

    Raises `LLMParseError` if OpenAI returns output that cannot be parsed
    into the `LLMAnswer` schema. The action catches this and maps it to
    the no-answer response path.
    """
    client = get_openai_client()

    response = await client.responses.parse(
        model=LLMConfig.OPENAI_ANSWER_MODEL,
        input=[
            {"role": "system", "content": build_answer_system_prompt()},
            {
                "role": "user",
                "content": build_answer_user_prompt(
                    question=question,
                    conversation_turns=conversation_turns,
                    retrieved_chunks=retrieved_chunks,
                ),
            },
        ],
        text_format=LLMAnswer,
    )

    if response.output_parsed is None:
        raise LLMParseError("LLM answer response did not include parsed output")

    return response.output_parsed
