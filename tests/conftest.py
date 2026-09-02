import pytest

from yitam_mcp import server as server_module
from yitam_mcp.qdrant_store import FormattedResult, ResultMetadata

SAMPLE_RESULTS: list[FormattedResult] = [
    FormattedResult(
        text="Nội kinh nói về âm dương.",
        metadata=ResultMetadata(source="", score=0.91),
    )
]


@pytest.fixture
def stub_store(monkeypatch):
    """Neutralize the lifespan and record calls to store.search."""
    calls: list[dict] = []

    async def fake_initialize() -> None:
        return None

    async def fake_close() -> None:
        return None

    async def fake_search(query, limit=10, score_threshold=0.7, domains=None):
        calls.append(
            {
                "query": query,
                "limit": limit,
                "score_threshold": score_threshold,
                "domains": domains,
            }
        )
        return SAMPLE_RESULTS

    monkeypatch.setattr(server_module.store, "initialize", fake_initialize)
    monkeypatch.setattr(server_module.store, "close", fake_close)
    monkeypatch.setattr(server_module.store, "search", fake_search)
    return calls
