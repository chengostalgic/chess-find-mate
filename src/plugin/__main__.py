"""The MCP server: each call's input built into its contract class, its output checked against its own."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from slimconfig import build_output, output_schema, plain_output

from contract import TOOLS, Tool
from plugin import check_mate_line, find_forced_mate

server = Server("chess-forced-mate")
# NanoAgent names the one folder this plugin may write to.
WORKSPACE_ENV = "NANOAGENT_WORKSPACE"
# Each tool's implementation: (its input, the workspace) -> its output, as contract.TOOLS types them.
IMPLEMENTATIONS = {Tool.FIND_FORCED_MATE: find_forced_mate, Tool.CHECK_MATE_LINE: check_mate_line}
DESCRIPTIONS = {
    Tool.FIND_FORCED_MATE: "Find forced mate within 1, 2, or 3 attacker moves from a six-field FEN; "
    "prove every legal defense. A budget error is undecided, not no mate.",
    Tool.CHECK_MATE_LINE: "Check up to 12 UCI moves from a six-field FEN for legality and final checkmate; "
    "a legal mating line alone does not prove forced mate.",
}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=tool.value,
            description=DESCRIPTIONS[tool],
            inputSchema=output_schema(given),
            outputSchema=output_schema(made),
        )
        for tool, (given, made) in TOOLS.items()
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    # A failure raises; the MCP server returns it as an error result.
    tool = Tool(name)
    given, made = TOOLS[tool]
    output = IMPLEMENTATIONS[tool](build_output(arguments, given), Path(os.environ[WORKSPACE_ENV]))
    if not isinstance(output, made):
        raise TypeError(f"{name} returned {type(output).__name__}, not {made.__name__}")
    return plain_output(output)


def main() -> None:
    if WORKSPACE_ENV not in os.environ:
        raise SystemExit(f"{WORKSPACE_ENV} is not set: NanoAgent passes the plugin's workspace folder")
    if set(IMPLEMENTATIONS) != set(Tool):
        raise SystemExit("IMPLEMENTATIONS must implement every contract.Tool")

    async def run() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(run)


if __name__ == "__main__":
    main()
