# YITAM FastMCP Server

Semantic search over a Qdrant knowledge base, exposed over the Model Context Protocol.

This is a Python/[FastMCP](https://gofastmcp.com) port of the TypeScript
[`yitam-mcp`](https://github.com/hadv/yitam-mcp) server. The port exists to get a
working **Streamable HTTP** transport: the TypeScript server only ever shipped stdio,
and its one attempt at SSE (PR #11) held a single global transport object, so it could
serve only one client at a time and was reverted.

## Features

- One tool, `query_domain_knowledge`: semantic search with optional domain filtering
- Transports: `stdio`, `http` (Streamable HTTP), and `sse` (deprecated, legacy clients)
- Optional shared bearer token on the network transports
- Gemini embeddings (`gemini-embedding-001`), Qdrant vector search
- Query-only: never creates or writes to a collection

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- A Qdrant instance with a pre-indexed collection
- A Google Gemini API key

## Setup

```bash
uv sync
cp .env.example .env   # then fill it in
```

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `TRANSPORT` | `stdio` | `stdio`, `http`, or `sse` |
| `HOST` | `127.0.0.1` | Bind address for `http`/`sse` |
| `PORT` | `3000` | Bind port for `http`/`sse` |
| `MCP_AUTH_TOKEN` | _(empty)_ | Shared bearer token; empty disables auth |
| `COLLECTION_NAME` | `vito` | Qdrant collection to query |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `QDRANT_API_KEY` | _(none)_ | Qdrant API key |
| `GEMINI_API_KEY` | _(none)_ | **Required.** Google Gemini API key |
| `GEMINI_MODEL` | `gemini-embedding-001` | Embedding model |
| `GEMINI_EMBEDDING_DIMENSIONS` | _(model default: 3072)_ | Optional dimension reduction |
| `DEFAULT_LIMIT` | `10` | Default result count |
| `MIN_SCORE_THRESHOLD` | `0.7` | Default similarity threshold |
| `MAX_RESULTS` | `20` | Hard cap on `limit` |
| `LOG_LEVEL` | `INFO` | Python log level |

Env var names match the TypeScript server's, so an existing `.env` can be copied
across unchanged.

> **`GEMINI_EMBEDDING_DIMENSIONS` must match the dimension your collection was built
> with.** `gemini-embedding-001` returns 3072 dimensions by default; if the collection
> expects 768, queries fail with
> `Vector dimension error: expected dim: 768, got 3072`. The TypeScript server
> swallowed that error and returned an empty result list, so the mismatch looked like
> "no matches found" rather than a misconfiguration.

## Running

```bash
# stdio (local MCP clients such as Claude Desktop)
uv run python -m yitam_mcp.server

# Streamable HTTP on http://0.0.0.0:3000/mcp
TRANSPORT=http HOST=0.0.0.0 MCP_AUTH_TOKEN=secret uv run python -m yitam_mcp.server
```

HTTP clients authenticate with `Authorization: Bearer <MCP_AUTH_TOKEN>`.

> `sse` is deprecated in the MCP spec and superseded by Streamable HTTP. It is kept
> only for clients that cannot speak the newer transport.

### Claude Desktop (stdio)

```json
{
  "mcpServers": {
    "yitam": {
      "command": "uv",
      "args": ["--directory", "/path/to/yitam-fast-mcp", "run", "python", "-m", "yitam_mcp.server"]
    }
  }
}
```

## Docker

```bash
./deploy.sh
```

Builds the image, replaces any running `yitam-fast-mcp` container, and waits for the
health check. The container defaults to `TRANSPORT=http` on port 3000.

## Development

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

## Porting notes

Two behaviours are load-bearing for compatibility with an already-indexed collection:

1. **Embeddings carry no task type.** The TypeScript `generateEmbedding` accepted a
   `taskType` argument and never forwarded it to the API, so the stored vectors were
   produced without one. Sending a task type here would move query vectors into a
   different embedding space and silently degrade retrieval. `tests/test_embedding.py`
   pins this.
2. **The tool's wire contract is unchanged** — tool name, the full description text,
   and the parameter names `query` / `domains` / `limit` / `scoreThreshold`
   (camelCase, hence the non-idiomatic Python parameter name).

Deliberate changes from the TypeScript server:

- A failing Qdrant query raises instead of returning an empty list, so an outage is
  no longer indistinguishable from "no matches found".
- Logs go to stderr. The TypeScript server logged to stdout, which corrupts the
  JSON-RPC stream under the stdio transport.
- The Gemini client is created once rather than per request.
- Chroma support and the unused `cosineSimilarity` helper are dropped.

Two harmless differences remain in the generated JSON schema:

| Field | TypeScript | Python |
| --- | --- | --- |
| `limit` | `"type": "number"` | `"type": "integer"` — rejects fractional limits |
| `domains` | `"type": "array"` | `anyOf: [array, null]` with `"default": null` — also accepts an explicit `null` |

Tool name, description, `required`, and every parameter name are byte-identical;
`tests/test_server.py` pins them.

## License

Apache License 2.0 - see [LICENSE](LICENSE).
