FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install app dependencies
COPY rossum-agent rossum-agent
RUN cd rossum-agent && uv sync --extra streamlit

# Expose the port the app runs on
EXPOSE 8501

ENV PYTHONUNBUFFERED=1
WORKDIR /app/rossum-agent
CMD ["uv", "run", "rossum-agent"]
