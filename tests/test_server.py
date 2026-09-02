"""End-to-end tests over the real MCP protocol, using FastMCP's in-memory client."""

import pytest
from fastmcp import Client

from yitam_mcp.server import TOOL_DESCRIPTION, mcp


@pytest.fixture
async def client(stub_store):
    async with Client(mcp) as client:
        yield client


class TestToolContract:
    """The wire contract must stay identical to the TypeScript server."""

    async def test_tool_name_and_description(self, client):
        tools = await client.list_tools()

        assert [t.name for t in tools] == ["query_domain_knowledge"]
        assert tools[0].description == TOOL_DESCRIPTION

    async def test_input_schema_properties(self, client):
        schema = (await client.list_tools())[0].input_schema

        assert set(schema["properties"]) == {"query", "domains", "limit", "scoreThreshold"}
        assert schema["required"] == ["query"]

    async def test_defaults_match_the_typescript_server(self, client):
        props = (await client.list_tools())[0].input_schema["properties"]

        assert props["limit"]["default"] == 10
        assert props["scoreThreshold"]["default"] == 0.7
        assert props["domains"]["default"] is None


class TestQueryDomainKnowledge:
    async def test_returns_results_on_success(self, client, stub_store):
        result = await client.call_tool("query_domain_knowledge", {"query": "đông y"})

        assert result.data == {
            "success": True,
            "results": [
                {
                    "text": "Nội kinh nói về âm dương.",
                    "metadata": {"source": "", "score": 0.91},
                }
            ],
        }

    async def test_applies_defaults(self, client, stub_store):
        await client.call_tool("query_domain_knowledge", {"query": "đông y"})

        assert stub_store == [
            {"query": "đông y", "limit": 10, "score_threshold": 0.7, "domains": None}
        ]

    async def test_forwards_domains_and_overrides(self, client, stub_store):
        await client.call_tool(
            "query_domain_knowledge",
            {
                "query": "phong thủy",
                "domains": ["phong thủy", "âm dương ngũ hành"],
                "limit": 3,
                "scoreThreshold": 0.5,
            },
        )

        assert stub_store == [
            {
                "query": "phong thủy",
                "limit": 3,
                "score_threshold": 0.5,
                "domains": ["phong thủy", "âm dương ngũ hành"],
            }
        ]

    @pytest.mark.parametrize("limit", [0, -1, 21])
    async def test_rejects_out_of_range_limit(self, client, stub_store, limit):
        result = await client.call_tool(
            "query_domain_knowledge", {"query": "q", "limit": limit}
        )

        assert result.data == {"success": False, "error": "Limit must be between 1 and 20"}
        assert stub_store == []

    @pytest.mark.parametrize("threshold", [-0.1, 1.5])
    async def test_rejects_out_of_range_score_threshold(self, client, stub_store, threshold):
        result = await client.call_tool(
            "query_domain_knowledge", {"query": "q", "scoreThreshold": threshold}
        )

        assert result.data == {
            "success": False,
            "error": "Score threshold must be between 0 and 1",
        }
        assert stub_store == []

    async def test_store_failure_is_reported_not_swallowed(self, client, monkeypatch):
        from yitam_mcp import server as server_module

        async def boom(*args, **kwargs):
            raise ConnectionError("qdrant is down")

        monkeypatch.setattr(server_module.store, "search", boom)

        result = await client.call_tool("query_domain_knowledge", {"query": "q"})

        assert result.data == {"success": False, "error": "qdrant is down"}
