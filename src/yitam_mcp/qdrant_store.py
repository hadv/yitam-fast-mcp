"""Qdrant-backed semantic search.

This server is query-only: it never creates or writes to a collection.
"""

import logging
from typing import TypedDict

from qdrant_client import AsyncQdrantClient, models

from .config import settings
from .embedding import generate_embedding

logger = logging.getLogger(__name__)

# Payload field holding the text we return. Matches the indexing pipeline.
PAYLOAD_FIELD = "enhancedContent"
# Payload field holding the domain tags a document belongs to.
DOMAIN_FIELD = "domains"


class ResultMetadata(TypedDict):
    source: str
    score: float


class FormattedResult(TypedDict):
    text: str
    metadata: ResultMetadata


def _normalize_domains(domains: list[str] | None) -> list[str]:
    """Lower-case and trim domain tags, dropping blanks.

    An all-blank list normalizes to empty, which the caller treats as "no filter" —
    the same as not passing domains at all.
    """
    if not domains:
        return []
    return [stripped for d in domains if (stripped := d.strip().lower())]


class QdrantStore:
    """Thin wrapper over the Qdrant client holding the search query we care about."""

    def __init__(self) -> None:
        self._client: AsyncQdrantClient | None = None
        self.collection_name = settings.collection_name

    @property
    def client(self) -> AsyncQdrantClient:
        if self._client is None:
            raise RuntimeError("Qdrant client not initialized")
        return self._client

    async def initialize(self) -> None:
        self._client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            check_compatibility=False,
        )
        collections = await self._client.get_collections()
        if any(c.name == self.collection_name for c in collections.collections):
            logger.info("Using existing Qdrant collection %s.", self.collection_name)
        else:
            logger.warning(
                "Collection %s does not exist. This MCP is query-only.",
                self.collection_name,
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def search(
        self,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.7,
        domains: list[str] | None = None,
    ) -> list[FormattedResult]:
        query_embedding = await generate_embedding(query)
        normalized_domains = _normalize_domains(domains)

        query_filter = (
            models.Filter(
                must=[
                    models.FieldCondition(
                        key=DOMAIN_FIELD,
                        match=models.MatchAny(any=list(normalized_domains)),
                    )
                ]
            )
            if normalized_domains
            else None
        )

        try:
            response = await self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=[PAYLOAD_FIELD],
                query_filter=query_filter,
            )
        except Exception:
            # Unlike the TypeScript version, we do not swallow this into an empty
            # result list: a Qdrant outage must not look like "no matches found".
            logger.exception("Error searching Qdrant collection %s", self.collection_name)
            raise

        return [
            FormattedResult(
                text=str((point.payload or {}).get(PAYLOAD_FIELD) or ""),
                metadata=ResultMetadata(source="", score=point.score),
            )
            for point in response.points
        ]
