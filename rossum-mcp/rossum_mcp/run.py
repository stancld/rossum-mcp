#!/usr/bin/env python3
from __future__ import annotations

from rossum_mcp.server import RossumMCPServer


def main() -> None:
    config = RossumMCPServer.Config.from_env()
    server = RossumMCPServer(config)
    server.run()


if __name__ == "__main__":
    main()
