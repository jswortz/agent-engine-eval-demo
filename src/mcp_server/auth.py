"""JWT authentication utilities for the BYO MCP server.

Generates RSA key pairs, creates signed JWT tokens, and configures a
JWTVerifier for token validation. Models the production pattern where
Agent Identity issues tokens that agents present as Bearer tokens.
"""

from __future__ import annotations

import os
import json
from pathlib import Path

from fastmcp.server.auth import JWTVerifier
from fastmcp.server.auth.providers.jwt import RSAKeyPair

ISSUER = "demo-mcp-user-service"
AUDIENCE = "mcp-user-service"
KEY_FILE = Path(__file__).parent / ".keys.json"

_key_pair: RSAKeyPair | None = None


def _get_or_create_keys() -> RSAKeyPair:
    """Load persisted keys or generate a new RSA key pair.

    Keys are saved to a local JSON file so the same key pair is reused
    across server restarts during development. In production, keys would
    come from Secret Manager or Agent Identity.
    """
    global _key_pair
    if _key_pair is not None:
        return _key_pair

    if KEY_FILE.exists():
        data = json.loads(KEY_FILE.read_text())
        from pydantic import SecretStr
        _key_pair = RSAKeyPair(
            private_key=SecretStr(data["private_key"]),
            public_key=data["public_key"],
        )
    else:
        _key_pair = RSAKeyPair.generate()
        KEY_FILE.write_text(json.dumps({
            "private_key": _key_pair.private_key.get_secret_value(),
            "public_key": _key_pair.public_key,
        }))

    return _key_pair


def create_demo_token(
    subject: str = "finance-agent",
    scopes: list[str] | None = None,
    expires_in_seconds: int = 3600,
) -> str:
    """Create a signed JWT for the demo agent.

    Args:
        subject: The agent or user identity (maps to 'sub' claim).
        scopes: OAuth scopes granted to this token.
        expires_in_seconds: Token lifetime.

    Returns:
        Signed JWT string.
    """
    keys = _get_or_create_keys()
    return keys.create_token(
        subject=subject,
        issuer=ISSUER,
        audience=AUDIENCE,
        scopes=scopes or ["read", "write"],
        expires_in_seconds=expires_in_seconds,
    )


def get_verifier() -> JWTVerifier:
    """Return a JWTVerifier configured with the demo public key."""
    keys = _get_or_create_keys()
    return JWTVerifier(
        public_key=keys.public_key,
        issuer=ISSUER,
        audience=AUDIENCE,
    )


def get_public_key() -> str:
    """Return the PEM-encoded public key for external consumers."""
    return _get_or_create_keys().public_key
