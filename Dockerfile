FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install app dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
