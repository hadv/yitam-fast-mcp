#!/bin/bash

set -euo pipefail

if [ ! -f .env ]; then
    echo "No .env file found. Please create one based on .env.example"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker first."
    exit 1
fi

# Only PORT is needed by this script; the container reads the rest via --env-file.
PORT="$(grep -E '^PORT=' .env | tail -n1 | cut -d= -f2- | tr -d '"'"'"' ' || true)"
PORT="${PORT:-3000}"

echo "Building Docker image..."
docker build -t yitam-fast-mcp:production .

if docker ps -a --format '{{.Names}}' | grep -qx yitam-fast-mcp; then
    echo "Stopping existing container..."
    docker stop yitam-fast-mcp > /dev/null || true
    docker rm yitam-fast-mcp > /dev/null || true
fi

echo "Starting container on port ${PORT}..."
docker run -d \
    --name yitam-fast-mcp \
    --restart unless-stopped \
    -p "${PORT}:3000" \
    --env-file .env \
    yitam-fast-mcp:production

echo "Waiting for the application to become healthy..."
for i in {1..30}; do
    status="$(docker inspect --format '{{.State.Health.Status}}' yitam-fast-mcp 2>/dev/null || echo unknown)"
    case "$status" in
        healthy)
            echo "Application is running and healthy!"
            exit 0
            ;;
        unhealthy)
            echo "Container reported unhealthy. Logs:"
            docker logs yitam-fast-mcp
            exit 1
            ;;
    esac
    echo "Waiting for container to be healthy... ($i/30)"
    sleep 2
done

echo "Container did not become healthy within 60 seconds. Please check logs:"
docker logs yitam-fast-mcp
exit 1
