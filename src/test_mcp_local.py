"""Local end-to-end test: ADK agent + BYO MCP server via stdio.

Spawns the MCP server as a subprocess, creates an agent with McpToolset,
and runs test queries to validate tool discovery and execution.

Usage:
    uv run python src/test_mcp_local.py
"""

from __future__ import annotations

import asyncio
import os

import vertexai
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.genai import types
from mcp import StdioServerParameters

PROJECT = "wortz-project-352116"
LOCATION = "us-central1"
MODEL = "gemini-2.5-flash"

TEST_QUERIES = [
    "List all users in the database.",
    "Get the profile for user-001.",
    "Update the email for user-002 to bob.new@example.com.",
    "Who is in the Security department?",
]


async def run_test():
    vertexai.init(project=PROJECT, location=LOCATION)
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", PROJECT)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", LOCATION)

    toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uv",
                args=["run", "python", "-m", "src.mcp_server.server"],
            ),
            timeout=15.0,
        ),
    )

    agent = Agent(
        model=MODEL,
        name="test_user_agent",
        instruction=(
            "You are an agent that manages user accounts via the User Service. "
            "Use the available tools to look up user profiles, list users, "
            "and update user information when asked."
        ),
        tools=[toolset],
    )

    runner = InMemoryRunner(agent=agent, app_name="test_mcp_app")
    user_id = "test-user"

    print("=" * 70)
    print("BYO MCP Local Test — Agent + MCP Server via stdio")
    print("=" * 70)

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n--- Query {i}: {query}")

        session = await runner.session_service.create_session(
            app_name="test_mcp_app",
            user_id=user_id,
        )

        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)],
        )

        response_parts = []
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_parts.append(part.text)
                    elif part.function_call:
                        print(f"    [tool_call] {part.function_call.name}({dict(part.function_call.args) if part.function_call.args else {}})")
                    elif part.function_response:
                        resp_data = dict(part.function_response.response) if part.function_response.response else {}
                        print(f"    [tool_result] {part.function_response.name} -> {str(resp_data)[:200]}")

        response = " ".join(response_parts)
        print(f"    [response] {response[:300]}")

    await toolset.close()
    print("\n" + "=" * 70)
    print("Test complete.")


if __name__ == "__main__":
    asyncio.run(run_test())
