from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from qdrant_client import models

from yitam_mcp import qdrant_store
from yitam_mcp.qdrant_store import QdrantStore, _normalize_domains


def _point(text: str, score: float):
    return SimpleNamespace(payload={"enhancedContent": text}, score=score)


@pytest.fixture
def store(monkeypatch):
    async def fake_embedding(text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(qdrant_store, "generate_embedding", fake_embedding)

    store = QdrantStore()
    store.collection_name = "yitam_test"
    store._client = AsyncMock()
    store._client.query_points.return_value = SimpleNamespace(
        points=[_point("Nội kinh nói về âm dương.", 0.91), _point("", 0.75)]
    )
    return store


class TestNormalizeDomains:
    def test_lowercases_and_trims(self):
        assert _normalize_domains(["  Đông Y ", "PHONG THỦY"]) == ["đông y", "phong thủy"]

    def test_drops_blanks(self):
        assert _normalize_domains(["", "   ", "đông y"]) == ["đông y"]

    def test_none_and_all_blank_normalize_to_empty(self):
        assert _normalize_domains(None) == []
        assert _normalize_domains(["  "]) == []


class TestSearch:
    async def test_query_shape_matches_typescript_server(self, store):
        await store.search("đông y", limit=5, score_threshold=0.8)

        kwargs = store._client.query_points.await_args.kwargs
        assert kwargs["collection_name"] == "yitam_test"
        assert kwargs["query"] == [0.1, 0.2, 0.3]
        assert kwargs["limit"] == 5
        assert kwargs["score_threshold"] == 0.8
        assert kwargs["with_payload"] == ["enhancedContent"]

    async def test_domains_become_a_match_any_filter(self, store):
        await store.search("q", domains=["  Đông Y ", "y học cổ truyền"])

        assert store._client.query_points.await_args.kwargs["query_filter"] == models.Filter(
            must=[
                models.FieldCondition(
                    key="domains",
                    match=models.MatchAny(any=["đông y", "y học cổ truyền"]),
                )
            ]
        )

    @pytest.mark.parametrize("domains", [None, [], ["   "]])
    async def test_no_filter_without_usable_domains(self, store, domains):
        await store.search("q", domains=domains)
        assert store._client.query_points.await_args.kwargs["query_filter"] is None

    async def test_maps_points_to_formatted_results(self, store):
        results = await store.search("q")

        assert results == [
            {"text": "Nội kinh nói về âm dương.", "metadata": {"source": "", "score": 0.91}},
            {"text": "", "metadata": {"source": "", "score": 0.75}},
        ]

    async def test_missing_payload_yields_empty_text(self, store):
        store._client.query_points.return_value = SimpleNamespace(
            points=[SimpleNamespace(payload=None, score=0.5)]
        )
        results = await store.search("q")
        assert results == [{"text": "", "metadata": {"source": "", "score": 0.5}}]

    async def test_qdrant_failure_propagates(self, store):
        """A Qdrant outage must not be reported as 'no matches found'."""
        store._client.query_points.side_effect = ConnectionError("qdrant is down")

        with pytest.raises(ConnectionError, match="qdrant is down"):
            await store.search("q")

    async def test_search_before_initialize_raises(self, monkeypatch):
        async def fake_embedding(text: str) -> list[float]:
            return [0.1]

        monkeypatch.setattr(qdrant_store, "generate_embedding", fake_embedding)
        with pytest.raises(RuntimeError, match="not initialized"):
            await QdrantStore().search("q")
