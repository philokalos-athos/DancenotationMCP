@echo off
set PYTHONPATH=C:\Users\moonw\DancenotationMCP\src
REM stdio_main is the MCP entry point. Do not point this at
REM dancenotation_mcp.mcp_server.server -- that module's main() speaks
REM LSP-style Content-Length framing, which MCP's NDJSON stdio transport
REM never sends, so it reads EOF and exits 0 before the handshake lands.
C:\Python314\python.exe -m dancenotation_mcp.mcp_server.stdio_main
