#!/usr/bin/env bash
# Set up Agent Identity connectors and bind them to the deployed agent.
#
# This script demonstrates the production pattern for OAuth-based auth
# between agents and BYO MCP servers. It creates:
#   1. A 2-legged OAuth connector (machine-to-machine, no user consent)
#   2. A binding between the connector and the deployed agent
#
# In production, Agent Identity manages:
#   - SPIFFE-based agent identity (auto-provisioned X.509 certs)
#   - Encrypted credential vault (Auth Manager)
#   - Automatic token refresh and DPoP-bound access tokens
#
# Prerequisites:
#   - gcloud CLI with alpha components
#   - Agent deployed to Agent Engine (run deploy_mcp_agent.py first)
#   - Agent Identity API enabled
#
# Usage:
#   export AGENT_ENGINE_ID="reasoningEngines/1234567890"
#   export MCP_SERVER_URL="https://user-service-mcp-HASH.run.app"
#   bash scripts/setup_agent_identity.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-wortz-project-352116}"
PROJECT_NUMBER="${PROJECT_NUMBER:-679926387543}"
LOCATION="${LOCATION:-us-central1}"
CONNECTOR_NAME="user-service-mcp-auth"

if [[ -z "${AGENT_ENGINE_ID:-}" ]]; then
    echo "ERROR: AGENT_ENGINE_ID is required (e.g. 'reasoningEngines/1234567890')"
    exit 1
fi

if [[ -z "${MCP_SERVER_URL:-}" ]]; then
    echo "ERROR: MCP_SERVER_URL is required (e.g. 'https://user-service-mcp-HASH.run.app')"
    exit 1
fi

echo "=== Agent Identity: OAuth Connector Setup ==="
echo "  Project:    ${PROJECT_ID}"
echo "  Location:   ${LOCATION}"
echo "  Connector:  ${CONNECTOR_NAME}"
echo "  Agent:      ${AGENT_ENGINE_ID}"
echo "  MCP Server: ${MCP_SERVER_URL}"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Create a 2-legged OAuth connector
# ---------------------------------------------------------------------------
# 2-legged OAuth is machine-to-machine: the agent authenticates with its own
# credentials (client_id + client_secret) without requiring user consent.
# Agent Identity stores these credentials in an encrypted vault and
# automatically manages token refresh.

echo "[1/4] Creating 2-legged OAuth connector..."
echo "  NOTE: In this demo, we use placeholder credentials."
echo "  In production, these come from your MCP server's OAuth configuration."

# For the demo, we generate placeholder credentials.
# In production, these would be real OAuth client credentials from your IdP.
CLIENT_ID="demo-mcp-client-$(date +%s)"
CLIENT_SECRET="demo-secret-$(openssl rand -hex 16)"
TOKEN_URL="${MCP_SERVER_URL}/oauth/token"

gcloud alpha agent-identity connectors create "${CONNECTOR_NAME}" \
    --location="${LOCATION}" \
    --project="${PROJECT_ID}" \
    --two-legged-oauth-token-url="${TOKEN_URL}" \
    --two-legged-oauth-client-id="${CLIENT_ID}" \
    --two-legged-oauth-client-secret="${CLIENT_SECRET}" \
    2>&1 || echo "  (Connector may already exist — continuing)"

echo ""

# ---------------------------------------------------------------------------
# Step 2: Verify the connector
# ---------------------------------------------------------------------------
echo "[2/4] Verifying connector..."
gcloud alpha agent-identity connectors describe "${CONNECTOR_NAME}" \
    --location="${LOCATION}" \
    --project="${PROJECT_ID}" \
    --format="yaml(name,state,twoLeggedOauth)" \
    2>&1 || echo "  (Connector describe may require additional permissions)"

echo ""

# ---------------------------------------------------------------------------
# Step 3: Bind the connector to the agent via Agent Registry
# ---------------------------------------------------------------------------
echo "[3/4] Creating auth binding (connector → agent)..."

BINDING_NAME="user-agent-mcp-binding"
SOURCE_ID="projects/${PROJECT_NUMBER}/locations/${LOCATION}/${AGENT_ENGINE_ID}"
AUTH_PROVIDER="projects/${PROJECT_ID}/locations/${LOCATION}/connectors/${CONNECTOR_NAME}"

gcloud alpha agent-registry bindings create "${BINDING_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${LOCATION}" \
    --source-identifier="${SOURCE_ID}" \
    --auth-provider="${AUTH_PROVIDER}" \
    2>&1 || echo "  (Binding may already exist — continuing)"

echo ""

# ---------------------------------------------------------------------------
# Step 4: Verify the binding
# ---------------------------------------------------------------------------
echo "[4/4] Verifying binding..."
gcloud alpha agent-registry bindings describe "${BINDING_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${LOCATION}" \
    --format="yaml(name,sourceIdentifier,authProvider)" \
    2>&1 || echo "  (Binding describe may require additional permissions)"

echo ""
echo "=== Agent Identity Setup Complete ==="
echo ""
echo "What Agent Identity provides:"
echo "  1. SPIFFE ID:  spiffe://agents.global.org-${PROJECT_NUMBER}.system.id.goog/..."
echo "     → Unique cryptographic identity for the agent"
echo ""
echo "  2. X.509 Certificate:"
echo "     → Auto-provisioned at deployment, 24h validity, auto-renewed"
echo "     → Cannot be impersonated or shared across workloads"
echo ""
echo "  3. DPoP-Bound Access Tokens:"
echo "     → Demonstrates Proof-of-Possession (cannot be replayed)"
echo "     → Cryptographically bound to the agent's certificate"
echo ""
echo "  4. Auth Manager:"
echo "     → Encrypted credential vault for OAuth tokens"
echo "     → Automatic token refresh for 2-legged and 3-legged flows"
echo ""
echo "Security features for BYO MCP:"
echo "  - Model Armor screens tools/call requests and responses"
echo "  - Tool annotations (destructiveHint) enable policy enforcement"
echo "  - VPC Service Controls (Preview) for perimeter protection"
echo "  - Audit logs show agent identity + user identity for each action"
