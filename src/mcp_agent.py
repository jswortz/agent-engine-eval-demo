"""ADK agent that consumes a BYO MCP server via McpToolset.

Supports two connection modes:
  - Local (stdio): Spawns the MCP server as a subprocess. No auth needed.
  - Remote (Streamable HTTP): Connects to a deployed MCP server with Bearer JWT.

Usage:
  # Create local agent (for testing)
  agent = create_local_agent()

  # Create remote agent (for deployment)
  agent = create_remote_agent(mcp_url="https://...", token="eyJ...")
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from mcp import StdioServerParameters

MODEL = "gemini-2.5-flash"
AGENT_NAME = "user_management_agent"
AGENT_INSTRUCTION = (
    "You are an agent that manages user accounts via the User Service. "
    "Use the available tools to look up user profiles, list users, "
    "and update user information when asked. "
    "Always confirm the user_id before making changes. "
    "When listing users, present results in a clear table format."
)


def create_local_agent() -> Agent:
    """Create an agent that connects to the MCP server via stdio (local dev)."""
    toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uv",
                args=["run", "python", "-m", "src.mcp_server.server"],
            ),
            timeout=15.0,
        ),
    )

    return Agent(
        model=MODEL,
        name=AGENT_NAME,
        instruction=AGENT_INSTRUCTION,
        tools=[toolset],
    )


def create_remote_agent(mcp_url: str, token: str) -> Agent:
    """Create an agent that connects to a remote MCP server with JWT auth.

    Args:
        mcp_url: Full URL to the MCP server (e.g. https://service.run.app/mcp).
        token: Signed JWT bearer token for authentication.
    """
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=mcp_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        ),
    )

    return Agent(
        model=MODEL,
        name=AGENT_NAME,
        instruction=AGENT_INSTRUCTION,
        tools=[toolset],
    )


def create_agent_from_env() -> Agent:
    """Create an agent using environment variables to determine connection mode.

    Set MCP_SERVER_URL and MCP_AUTH_TOKEN for remote mode.
    If unset, falls back to local stdio mode.
    """
    mcp_url = os.environ.get("MCP_SERVER_URL")
    mcp_token = os.environ.get("MCP_AUTH_TOKEN")

    if mcp_url and mcp_token:
        return create_remote_agent(mcp_url=mcp_url, token=mcp_token)
    return create_local_agent()
