"""Gemini embedding generation.

IMPORTANT — do not add `task_type` to the request.

The original TypeScript implementation accepted a `taskType` argument but never
forwarded it to the API (src/utils/embedding.ts in the yitam-mcp repo passed only
`model`, `contents` and `outputDimensionality`). The vectors already stored in the
production collection were therefore produced *without* a task type. Sending one
here would shift the embedding space and silently degrade retrieval quality
against that collection.
"""

import logging

from google import genai
from google.genai import types

from .config import settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Return the shared Gemini client, creating it on first use."""
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini embeddings")
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


async def generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for `text`."""
    config = (
        types.EmbedContentConfig(
            output_dimensionality=settings.gemini_embedding_dimensions
        )
        if settings.gemini_embedding_dimensions
        else None
    )

    response = await _get_client().aio.models.embed_content(
        model=settings.gemini_model,
        contents=[text],
        config=config,
    )

    if not response.embeddings:
        raise RuntimeError("No embeddings returned from API")

    values = response.embeddings[0].values
    if not values:
        raise RuntimeError("No values in embedding response")

    return values
