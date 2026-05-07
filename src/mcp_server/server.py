"""BYO MCP server with JWT authentication protecting a mock user database.

Three tools exposed:
  - get_user_profile: read-only lookup
  - list_users: read-only listing
  - update_user_email: destructive write

Auth is enforced on HTTP transports (Streamable HTTP / SSE) via JWTVerifier.
Stdio transport (local dev) bypasses auth — no HTTP headers available.

Usage:
  # Local development (stdio, no auth)
  uv run python src/mcp_server/server.py

  # Network deployment (streamable-http, JWT auth enforced)
  uv run python src/mcp_server/server.py --transport streamable-http --port 8080
"""

from __future__ import annotations

import argparse
import sys

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token

from src.mcp_server.mock_db import USERS
from src.mcp_server.auth import get_verifier


def create_server(*, require_auth: bool = True) -> FastMCP:
    """Create the MCP server, optionally with JWT auth."""
    auth = get_verifier() if require_auth else None
    mcp = FastMCP(name="user-service", auth=auth)

    @mcp.tool
    def get_user_profile(user_id: str) -> dict:
        """Gets a user profile from the user database.

        Args:
            user_id: The user identifier (e.g. 'user-001').

        Returns:
            User profile dict or error message.
        """
        token = get_access_token()
        caller = token.claims.get("sub", "unknown") if token else "anonymous (stdio)"
        print(f"[get_user_profile] caller={caller} user_id={user_id}", file=sys.stderr)

        user = USERS.get(user_id)
        if user is None:
            return {"error": f"User not found: {user_id}"}
        return user

    @mcp.tool
    def list_users() -> list[dict]:
        """Lists all user IDs and names in the database.

        Returns:
            List of dicts with user_id and name for each user.
        """
        token = get_access_token()
        caller = token.claims.get("sub", "unknown") if token else "anonymous (stdio)"
        print(f"[list_users] caller={caller}", file=sys.stderr)

        return [
            {"user_id": uid, "name": u["name"]}
            for uid, u in USERS.items()
        ]

    @mcp.tool
    def update_user_email(user_id: str, new_email: str) -> dict:
        """Updates a user's email address. This is a destructive operation.

        Args:
            user_id: The user identifier to update.
            new_email: The new email address.

        Returns:
            Confirmation dict with old and new email, or error.
        """
        token = get_access_token()
        caller = token.claims.get("sub", "unknown") if token else "anonymous (stdio)"
        print(f"[update_user_email] caller={caller} user_id={user_id} new_email={new_email}", file=sys.stderr)

        user = USERS.get(user_id)
        if user is None:
            return {"error": f"User not found: {user_id}"}

        old_email = user["email"]
        user["email"] = new_email
        return {
            "status": "updated",
            "user_id": user_id,
            "old_email": old_email,
            "new_email": new_email,
            "updated_by": caller,
        }

    return mcp


def main():
    parser = argparse.ArgumentParser(description="BYO MCP User Service")
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument("--port", type=int, default=8080, help="Port for HTTP transports")
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP transports")
    args = parser.parse_args()

    require_auth = args.transport != "stdio"
    mcp = create_server(require_auth=require_auth)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
