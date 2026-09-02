"""The load-bearing compatibility test: embeddings must not carry a task type.

The production collection was indexed by a TypeScript server that accepted a
`taskType` argument and then dropped it on the floor. Sending one now would move
the query vectors into a different embedding space than the stored documents.
"""

from types import SimpleNamespace

import pytest

from yitam_mcp import embedding


class _RecordingClient:
    def __init__(self) -> None:
        self.kwargs: dict = {}
        self.aio = SimpleNamespace(models=SimpleNamespace(embed_content=self._embed))

    async def _embed(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2, 0.3])])


@pytest.fixture
def recording_client(monkeypatch):
    client = _RecordingClient()
    monkeypatch.setattr(embedding, "_get_client", lambda: client)
    return client


async def test_request_carries_no_task_type(recording_client):
    await embedding.generate_embedding("đông y")

    assert "task_type" not in recording_client.kwargs
    config = recording_client.kwargs["config"]
    assert config is None or getattr(config, "task_type", None) is None


async def test_sends_model_and_contents(recording_client):
    vector = await embedding.generate_embedding("đông y")

    assert vector == [0.1, 0.2, 0.3]
    assert recording_client.kwargs["model"] == embedding.settings.gemini_model
    assert recording_client.kwargs["contents"] == ["đông y"]


async def test_output_dimensionality_only_when_configured(recording_client, monkeypatch):
    monkeypatch.setattr(embedding.settings, "gemini_embedding_dimensions", None)
    await embedding.generate_embedding("x")
    assert recording_client.kwargs["config"] is None

    monkeypatch.setattr(embedding.settings, "gemini_embedding_dimensions", 768)
    await embedding.generate_embedding("x")
    assert recording_client.kwargs["config"].output_dimensionality == 768


async def test_raises_when_no_embeddings_returned(monkeypatch):
    class _Empty(_RecordingClient):
        async def _embed(self, **kwargs):
            return SimpleNamespace(embeddings=[])

    monkeypatch.setattr(embedding, "_get_client", _Empty)
    with pytest.raises(RuntimeError, match="No embeddings returned"):
        await embedding.generate_embedding("x")


async def test_raises_when_embedding_has_no_values(monkeypatch):
    class _NoValues(_RecordingClient):
        async def _embed(self, **kwargs):
            return SimpleNamespace(embeddings=[SimpleNamespace(values=None)])

    monkeypatch.setattr(embedding, "_get_client", _NoValues)
    with pytest.raises(RuntimeError, match="No values in embedding response"):
        await embedding.generate_embedding("x")
