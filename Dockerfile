# ---- build ----
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first so they stay cached across source changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# ---- runtime ----
FROM python:3.12-slim-bookworm

WORKDIR /app
RUN useradd --create-home --uid 1000 app

# The venv holds an editable install pointing at /app/src, so both must keep
# the same paths they had in the build stage.
COPY --from=build --chown=app:app /app/.venv /app/.venv
COPY --from=build --chown=app:app /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    TRANSPORT=http \
    HOST=0.0.0.0 \
    PORT=3000

USER app
EXPOSE 3000

# Confirms the server is actually accepting connections. The MCP endpoint itself
# only answers well-formed POSTs, so a TCP check is the honest signal here.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,socket; socket.create_connection(('127.0.0.1', int(os.environ.get('PORT','3000'))), 3).close()"

CMD ["python", "-m", "yitam_mcp.server"]
