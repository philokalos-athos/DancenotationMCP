"""MCP server entry point using the official mcp SDK for proper protocol handling."""
from __future__ import annotations

import json
from mcp.server import Server
from mcp.server.stdio import stdio_server

from dancenotation_mcp.mcp_server.server import TOOL_SCHEMAS, TOOLS

app = Server("dancenotation-mcp")


@app.list_tools()
async def list_tools():
    from mcp.types import Tool
    return [
        Tool(
            name=name,
            description=schema["description"],
            inputSchema=schema["inputSchema"],
        )
        for name, schema in TOOL_SCHEMAS.items()
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    from mcp.types import TextContent
    if name not in TOOLS:
        raise ValueError(f"Unknown tool '{name}'")
    result = TOOLS[name](arguments)
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
