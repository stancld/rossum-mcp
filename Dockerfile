FROM python:3.13-slim

WORKDIR /rossum-mcp

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install app dependencies
COPY rossum_agent rossum_agent
COPY rossum_mcp rossum_mcp
COPY pyproject.toml uv.lock ./
RUN uv sync --extra agent --extra bedrock --extra streamlit --no-install-project

# Expose the port the app runs on
EXPOSE 8501

ENV PYTHONUNBUFFERED=1
CMD ["uv", "run", "streamlit", "run", "rossum_agent/app.py"]
