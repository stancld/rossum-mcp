FROM python:3.14-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY rossum-agent rossum-agent
RUN cd rossum-agent && uv sync --extra api --no-dev

FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

WORKDIR /app/rossum-agent

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=builder /app/rossum-agent /app/rossum-agent

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
CMD ["uv", "run", "rossum-agent-api", "--host", "0.0.0.0"]
