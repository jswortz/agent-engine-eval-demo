"""Deploy BYO MCP server to Cloud Run and ADK agent to Agent Engine.

Two-phase deployment:
  Phase A: Build + deploy the MCP server to Cloud Run
  Phase B: Deploy the ADK agent (with McpToolset) to Agent Engine

Usage:
    # Full pipeline: deploy MCP server + agent + generate traffic
    uv run python src/deploy_mcp_agent.py

    # Agent-only (MCP server already deployed):
    uv run python src/deploy_mcp_agent.py --mcp-url https://user-service-mcp-HASH.run.app/mcp

    # Skip Cloud Run deploy (use existing MCP server):
    uv run python src/deploy_mcp_agent.py --skip-mcp-deploy --mcp-url https://...
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

import google.auth
import google.auth.transport.requests
import requests
import vertexai
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from vertexai.agent_engines import AdkApp

from src.mcp_server.auth import create_demo_token

PROJECT = "wortz-project-352116"
PROJECT_NUMBER = "679926387543"
LOCATION = "us-central1"
STAGING_BUCKET = "gs://wortz-project-352116-vertex-staging-us-central1"
CLOUD_RUN_SERVICE = "user-service-mcp"
CLOUD_RUN_REGION = "us-central1"
IMAGE_NAME = f"gcr.io/{PROJECT}/{CLOUD_RUN_SERVICE}"


# ---------------------------------------------------------------------------
# Phase A: Deploy MCP server to Cloud Run
# ---------------------------------------------------------------------------

def deploy_mcp_server() -> str:
    """Build and deploy the MCP server to Cloud Run.

    Returns:
        The Cloud Run service URL.
    """
    print("\n[Phase A] Deploying MCP server to Cloud Run...")

    print("  Building container image...")
    subprocess.run(
        [
            "gcloud", "builds", "submit",
            "--tag", IMAGE_NAME,
            "--project", PROJECT,
            "src/mcp_server",
        ],
        check=True,
    )

    print("  Deploying to Cloud Run...")
    result = subprocess.run(
        [
            "gcloud", "run", "deploy", CLOUD_RUN_SERVICE,
            "--image", IMAGE_NAME,
            "--region", CLOUD_RUN_REGION,
            "--project", PROJECT,
            "--platform", "managed",
            "--allow-unauthenticated",
            "--port", "8080",
            "--set-env-vars", "TRANSPORT=streamable-http",
            "--format", "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    service_info = json.loads(result.stdout)
    service_url = service_info.get("status", {}).get("url", "")
    mcp_url = f"{service_url}/mcp"
    print(f"  MCP server deployed: {mcp_url}")
    return mcp_url


# ---------------------------------------------------------------------------
# Phase B: Deploy ADK agent to Agent Engine
# ---------------------------------------------------------------------------

def deploy_agent(mcp_url: str) -> str:
    """Deploy the ADK agent with McpToolset to Agent Engine.

    Args:
        mcp_url: URL of the deployed MCP server.

    Returns:
        Agent Engine resource name.
    """
    print("\n[Phase B] Deploying ADK agent to Agent Engine...")

    token = create_demo_token(subject="user-management-agent", scopes=["read", "write"])

    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=mcp_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        ),
    )

    agent = Agent(
        model="gemini-2.5-flash",
        name="user_management_agent",
        instruction=(
            "You are an agent that manages user accounts via the User Service. "
            "Use the available tools to look up user profiles, list users, "
            "and update user information when asked. "
            "Always confirm the user_id before making changes."
        ),
        tools=[toolset],
    )

    app = AdkApp(agent=agent, enable_tracing=True)
    client = vertexai.Client(project=PROJECT, location=LOCATION)

    engine = client.agent_engines.create(
        agent=app,
        config={
            "display_name": "User Management Agent (BYO MCP)",
            "staging_bucket": STAGING_BUCKET,
            "agent_framework": "google-adk",
            "requirements": [
                "google-cloud-aiplatform[adk,agent_engines]",
                "google-adk",
                "fastmcp>=3.2.4",
                "mcp>=1.9.0",
                "cryptography>=41.0.0",
                "opentelemetry-api",
                "opentelemetry-sdk",
                "opentelemetry-instrumentation-fastapi",
                "opentelemetry-instrumentation-httpx",
                "opentelemetry-exporter-gcp-logging",
            ],
            "env_vars": {
                "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
                "OTEL_SERVICE_NAME": "user-management-agent",
                "OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED": "true",
                "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
                "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
                "MCP_SERVER_URL": mcp_url,
            },
        },
    )

    resource_name = engine.api_resource.name
    print(f"  Agent deployed: {resource_name}")
    return resource_name


# ---------------------------------------------------------------------------
# Generate traffic
# ---------------------------------------------------------------------------

def generate_traffic(resource_name: str):
    """Send test queries to the deployed agent."""
    print("\n[Traffic] Generating test queries...")

    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)

    engine_id = resource_name.split("/")[-1]
    url = (
        f"https://{LOCATION}-aiplatform.googleapis.com/v1/"
        f"projects/{PROJECT}/locations/{LOCATION}/"
        f"reasoningEngines/{engine_id}:streamQuery"
    )

    queries = [
        "List all users in the database.",
        "Get the profile for user-003.",
        "What is the email for user-001?",
        "Update the email for user-005 to eva.updated@example.com.",
    ]

    for i, query in enumerate(queries, 1):
        print(f"\n  Query {i}: {query}")
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            json={"input": {"user_id": f"mcp-test-{i}", "message": query}},
            timeout=60,
        )

        texts = []
        for line in resp.text.strip().split("\n"):
            try:
                event = json.loads(line)
                for part in event.get("content", {}).get("parts", []):
                    if "text" in part:
                        texts.append(part["text"])
            except (json.JSONDecodeError, KeyError):
                pass

        response_text = " ".join(texts) if texts else "No response"
        print(f"  Response: {response_text[:200]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Deploy BYO MCP agent pipeline")
    parser.add_argument("--mcp-url", help="Use existing MCP server URL (skip deploy)")
    parser.add_argument("--skip-mcp-deploy", action="store_true", help="Skip MCP server deployment")
    parser.add_argument("--skip-traffic", action="store_true", help="Skip traffic generation")
    args = parser.parse_args()

    if args.mcp_url:
        mcp_url = args.mcp_url
    elif args.skip_mcp_deploy:
        print("ERROR: --skip-mcp-deploy requires --mcp-url", file=sys.stderr)
        sys.exit(1)
    else:
        mcp_url = deploy_mcp_server()

    resource_name = deploy_agent(mcp_url)
    print(f"\nAGENT_ENGINE_RESOURCE_NAME={resource_name}")

    if not args.skip_traffic:
        time.sleep(10)
        generate_traffic(resource_name)


if __name__ == "__main__":
    main()
