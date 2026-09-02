"""FastMCP server exposing the yitam domain-knowledge search tool."""

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from pydantic import Field

from .config import settings
from .qdrant_store import QdrantStore
from .tool_description import TOOL_DESCRIPTION

logger = logging.getLogger(__name__)

store = QdrantStore()


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    await store.initialize()
    try:
        yield {}
    finally:
        await store.close()


def _build_auth() -> StaticTokenVerifier | None:
    """Bearer-token auth for the network transports, when a token is configured."""
    if settings.transport == "stdio" or not settings.mcp_auth_token:
        return None
    return StaticTokenVerifier(tokens={settings.mcp_auth_token: {"client_id": "yitam"}})


mcp: FastMCP[Any] = FastMCP(
    name="yitam-server",
    version="1.0.0",
    lifespan=lifespan,
    auth=_build_auth(),
)


def _validate_search_params(limit: int, score_threshold: float) -> None:
    if limit <= 0 or limit > settings.max_results:
        raise ValueError(f"Limit must be between 1 and {settings.max_results}")
    if score_threshold < 0 or score_threshold > 1:
        raise ValueError("Score threshold must be between 0 and 1")


# `scoreThreshold` is camelCase on purpose: FastMCP derives the wire schema from this
# signature, and existing clients call the tool with the TypeScript server's names.
@mcp.tool(name="query_domain_knowledge", description=TOOL_DESCRIPTION)
async def query_domain_knowledge(
    query: Annotated[
        str, Field(description="The search query for retrieving domain knowledge")
    ],
    domains: Annotated[
        list[str] | None,
        Field(description="List of specific domains to search within (optional)"),
    ] = None,
    limit: Annotated[
        int,
        Field(description=f"Number of results to retrieve (max {settings.max_results})"),
    ] = settings.default_limit,
    scoreThreshold: Annotated[  # noqa: N803
        float, Field(description="Minimum similarity score threshold (0-1)")
    ] = settings.min_score_threshold,
) -> dict[str, Any]:
    try:
        _validate_search_params(limit, scoreThreshold)
        results = await store.search(query, limit, scoreThreshold, domains)
        return {"success": True, "results": results}
    except Exception as exc:
        logger.exception("Error in query_domain_knowledge")
        return {"success": False, "error": str(exc)}


def main() -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        # stderr only: stdout carries the JSON-RPC stream under the stdio transport.
        stream=sys.stderr,
    )

    if settings.transport == "stdio":
        logger.info("YITAM server starting on stdio")
        mcp.run()
        return

    if not settings.mcp_auth_token:
        logger.warning(
            "MCP_AUTH_TOKEN is not set - the %s endpoint is unauthenticated.",
            settings.transport,
        )
    logger.info(
        "YITAM server starting with %s transport on %s:%s",
        settings.transport,
        settings.host,
        settings.port,
    )
    mcp.run(transport=settings.transport, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
