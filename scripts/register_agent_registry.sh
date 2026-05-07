#!/usr/bin/env bash
# Register the BYO MCP server with Gemini Enterprise Agent Platform Agent Registry.
#
# Prerequisites:
#   - gcloud CLI with alpha components installed
#   - MCP server deployed to Cloud Run (run deploy_mcp_agent.py first)
#   - Agent Registry API enabled: gcloud services enable agentregistry.googleapis.com
#
# Usage:
#   export MCP_SERVER_URL="https://user-service-mcp-HASH-uc.a.run.app/mcp"
#   bash scripts/register_agent_registry.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-wortz-project-352116}"
LOCATION="${LOCATION:-us-central1}"
SERVICE_NAME="user-service-mcp"
DISPLAY_NAME="User Service MCP Server"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -z "${MCP_SERVER_URL:-}" ]]; then
    echo "ERROR: MCP_SERVER_URL environment variable is required."
    echo "  export MCP_SERVER_URL=\"https://user-service-mcp-HASH.run.app/mcp\""
    exit 1
fi

echo "=== Agent Registry: Register BYO MCP Server ==="
echo "  Project:  ${PROJECT_ID}"
echo "  Location: ${LOCATION}"
echo "  Service:  ${SERVICE_NAME}"
echo "  URL:      ${MCP_SERVER_URL}"
echo ""

# Step 1: Register the MCP server with its tool specification
echo "[1/3] Registering MCP server..."
gcloud alpha agent-registry services create "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${LOCATION}" \
    --display-name="${DISPLAY_NAME}" \
    --mcp-server-spec-type=tool-spec \
    --mcp-server-spec-content=@"${SCRIPT_DIR}/toolspec.json" \
    --interfaces=url="${MCP_SERVER_URL}",protocolBinding=HTTP_JSON

echo ""
echo "[2/3] Verifying registration..."
gcloud alpha agent-registry services describe "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${LOCATION}" \
    --format="yaml(name,displayName,mcpServerSpec,interfaces)"

echo ""
echo "[3/3] Listing all registered MCP servers..."
gcloud alpha agent-registry services list \
    --project="${PROJECT_ID}" \
    --location="${LOCATION}" \
    --format="table(name,displayName)"

echo ""
echo "=== Registration complete ==="
echo ""
echo "Tool annotations registered:"
echo "  get_user_profile  - readOnly=true,  destructive=false"
echo "  list_users        - readOnly=true,  destructive=false"
echo "  update_user_email - readOnly=false, destructive=true"
echo ""
echo "These annotations enable:"
echo "  - Model Armor screening of destructive tool calls"
echo "  - Agent Gateway policy enforcement"
echo "  - Tool discovery via Agent Registry search"
