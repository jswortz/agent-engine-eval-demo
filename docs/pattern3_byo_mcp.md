# Pattern 3: BYO MCP with OAuth and Agent Identity

> **Bring Your Own MCP server** on Gemini Enterprise Agent Platform with JWT-based OAuth authentication, Agent Identity integration, and Model Armor protection for tool calls.

**Source code**: `src/mcp_server/`, `src/mcp_agent.py`, `src/deploy_mcp_agent.py`
**Scripts**: `scripts/register_agent_registry.sh`, `scripts/setup_agent_identity.sh`
**Docs**: [Agent Identity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview) · [Agent Registry](https://docs.cloud.google.com/agent-registry/register-mcp-servers) · [Model Armor for MCP](https://docs.cloud.google.com/model-armor/model-armor-mcp-google-cloud-integration)

---

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Gemini Enterprise Agent Platform                │
│                                                                 │
│  ┌───────────────────┐         ┌──────────────────────────────┐ │
│  │   Agent Registry   │◄────────│  Register MCP Server         │ │
│  │  (tool discovery)  │         │  + tool annotations          │ │
│  └─────────┬─────────┘         │  (destructiveHint, etc.)     │ │
│            │                   └──────────────────────────────┘ │
│  ┌─────────▼─────────┐                                         │
│  │   Agent Engine     │                                         │
│  │  ┌──────────────┐  │         ┌──────────────────────────────┐│
│  │  │  ADK Agent    │  │  HTTP   │  BYO MCP Server (Cloud Run) ││
│  │  │  (McpToolset) │──┼────────►│  FastMCP + JWTVerifier       ││
│  │  │              │  │ Bearer  │  ┌────────────────────────┐  ││
│  │  └──────────────┘  │  JWT    │  │  Mock User Database    │  ││
│  └────────────────────┘         │  └────────────────────────┘  ││
│                                 └──────────────────────────────┘│
│  ┌────────────────────┐         ┌──────────────────────────────┐│
│  │  Agent Identity     │         │  Model Armor                 ││
│  │  SPIFFE + X.509    │         │  Screens tools/call          ││
│  │  DPoP tokens       │         │  requests & responses        ││
│  └────────────────────┘         └──────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Data flow:**
1. ADK Agent discovers MCP tools via `McpToolset` at startup
2. User query arrives → Agent decides to call an MCP tool
3. `McpToolset` sends `tools/call` with Bearer JWT to the MCP server
4. MCP server validates JWT via `JWTVerifier`, executes tool, returns result
5. Model Armor screens the request and response for prompt injection
6. Agent Registry logs tool invocation with agent identity audit trail

---

## 2. OAuth for MCP Tools

### Why MCP servers need authentication

MCP servers expose tools that can read, modify, or delete data. Without authentication:
- Any client can call destructive tools (`update_user_email`)
- No audit trail for who performed which action
- No scope-based access control

### JWT-based token validation

This demo uses `JWTVerifier` from FastMCP — a `TokenVerifier` that validates Bearer JWT tokens. This models the production pattern where Agent Identity issues tokens that agents present to downstream services.

```python
# Server side: validate incoming tokens
from fastmcp import FastMCP
from fastmcp.server.auth import JWTVerifier

verifier = JWTVerifier(
    public_key=PUBLIC_KEY,       # PEM-encoded RSA public key
    issuer="demo-mcp-user-service",
    audience="mcp-user-service",
)
mcp = FastMCP(name="user-service", auth=verifier)
```

```python
# Agent side: present token in headers
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mcp-server.run.app/mcp",
        headers={"Authorization": f"Bearer {jwt_token}"},
    ),
)
```

### Token identity propagation

Inside MCP tools, the agent's identity is available via `get_access_token()`:

```python
from fastmcp.server.dependencies import get_access_token

@mcp.tool
def update_user_email(user_id: str, new_email: str) -> dict:
    token = get_access_token()
    caller = token.claims.get("sub")  # "user-management-agent"
    # ... perform update, log caller identity
    return {"updated_by": caller, ...}
```

**JWT claims available:**

| Claim | Description | Example |
|-------|-------------|---------|
| `sub` | Agent or user identity | `"user-management-agent"` |
| `iss` | Token issuer | `"demo-mcp-user-service"` |
| `aud` | Intended audience | `"mcp-user-service"` |
| `scope` | Granted permissions | `"read write"` |
| `exp` | Expiration timestamp | `1720000000` |

---

## 3. Agent Identity Security Model

Agent Identity is Google's cryptographic identity system for agents. It provides three layers of security that go beyond traditional service account authentication.

### SPIFFE-based identity

Each deployed agent receives a unique [SPIFFE](https://spiffe.io/) identifier:

```
spiffe://agents.global.org-{ORG_ID}.system.id.goog/resources/{SERVICE}/{RESOURCE_PATH}
```

This identity is:
- **Unique**: Not shared across workloads or environments
- **Non-impersonatable**: Cryptographically bound to the agent's runtime
- **Usable in IAM**: Can be referenced in allow/deny policies as a principal

### X.509 certificates

Agent Identity auto-provisions X.509 certificates at deployment:

| Property | Value |
|----------|-------|
| Provisioning | Automatic at agent deployment |
| Validity | 24 hours |
| Renewal | Automatic (no downtime) |
| Storage | Agent runtime (never exported) |

### DPoP-bound access tokens

When an agent requests access tokens for Google Cloud services, Agent Identity issues **Demonstration of Proof-of-Possession (DPoP)** tokens:

- Token is cryptographically bound to the agent's X.509 certificate
- Cannot be replayed from a different runtime (prevents token theft)
- Enforces mTLS for Agent Gateway access

### Auth connectors for external services

For BYO MCP servers and other external tools, Agent Identity provides **auth connectors** (Preview):

| Connector Type | Use Case | User Consent |
|---------------|----------|-------------|
| **2-legged OAuth** | Machine-to-machine (agent's own authority) | No |
| **3-legged OAuth** | Act on behalf of a user (delegated authority) | Yes |
| **API Key** | Services requiring static keys (Maps, Weather) | No |

```bash
# Create a 2-legged OAuth connector
gcloud alpha agent-identity connectors create demo-mcp-auth \
    --two-legged-oauth-token-url="https://mcp-server.run.app/oauth/token" \
    --two-legged-oauth-client-id="$CLIENT_ID" \
    --two-legged-oauth-client-secret="$CLIENT_SECRET"

# Bind the connector to the agent
gcloud alpha agent-registry bindings create user-agent-binding \
    --source-identifier="projects/$PROJECT_NUMBER/locations/$LOCATION/reasoningEngines/$ID" \
    --auth-provider="projects/$PROJECT_ID/locations/$LOCATION/connectors/demo-mcp-auth"
```

**How it works at runtime:**
1. Agent needs to call the MCP server
2. Agent Identity retrieves credentials from the encrypted Auth Manager vault
3. Agent Identity performs the OAuth token exchange (client credentials grant)
4. The resulting access token is injected into the MCP tool call headers
5. No secrets are ever exposed to the agent's LLM context

---

## 4. Agent Registry and Tool Annotations

### Registering MCP servers

Agent Registry is the central hub for discovering and managing MCP servers:

```bash
gcloud alpha agent-registry services create user-service-mcp \
    --mcp-server-spec-type=tool-spec \
    --mcp-server-spec-content=@toolspec.json \
    --interfaces=url=$MCP_URL,protocolBinding=HTTP_JSON
```

### Tool annotations

Each tool in the spec can include security-relevant annotations:

```json
{
  "name": "update_user_email",
  "annotations": {
    "destructiveHint": true,    // Modifies or deletes data
    "readOnlyHint": false,      // Does NOT just read data
    "idempotentHint": true,     // Safe to retry
    "openWorldHint": false      // Does NOT make external network calls
  }
}
```

**What annotations enable:**
- **Agent Gateway** can enforce policies (e.g., block destructive tools without approval)
- **Model Armor** applies stricter screening to destructive tool calls
- **Audit logs** tag actions with annotation metadata for compliance review
- **Tool discovery** filters by annotation (e.g., "show me all read-only tools")

---

## 5. Model Armor for MCP

Model Armor provides proactive screening of MCP tool interactions to protect against prompt injection, data exfiltration, and malicious content in tool outputs.

### What gets screened

| MCP Operation | Screened? | What's Checked |
|--------------|-----------|----------------|
| `tools/call` request | Yes | Prompt injection in tool arguments |
| `tools/call` response | Yes | Sensitive data, malicious content in results |
| `prompts/get` request | Yes | Prompt injection attempts |
| `prompts/get` response | Yes | Malicious prompt content |
| `tools/list` | No | Discovery only, no data flow |
| `resources/*` | No | Resource metadata only |

### Configuration

```bash
gcloud model-armor floorsettings update \
    --full-uri="projects/$PROJECT_ID/locations/global/floorSetting" \
    --enable-floor-setting-enforcement=TRUE \
    --add-integrated-services=GOOGLE_MCP_SERVER \
    --google-mcp-server-enforcement-type=INSPECT_AND_BLOCK \
    --malicious-uri-filter-settings-enforcement=ENABLED
```

### How it works

1. Agent calls `tools/call` with tool name and arguments
2. Model Armor inspects the request for prompt injection patterns
3. If clean, the request is forwarded to the MCP server
4. MCP server processes the request and returns a result
5. Model Armor inspects the response for sensitive data or malicious content
6. If clean, the result is returned to the agent
7. If flagged, the request/response is blocked and logged to Cloud Logging

---

## 6. Security Comparison

| Aspect | No Auth | Static Token | JWT (this demo) | Agent Identity |
|--------|---------|-------------|-----------------|----------------|
| **Authentication** | None | Shared secret | Signed token | SPIFFE + X.509 |
| **Identity** | Anonymous | Shared across clients | Per-agent `sub` claim | Unique per-agent SPIFFE ID |
| **Token lifetime** | N/A | Infinite (until rotated) | Configurable (1h default) | 24h cert, auto-renewed |
| **Replay protection** | None | None | Expiration only | DPoP-bound (cryptographic) |
| **Credential storage** | N/A | App config / env vars | Generated at runtime | Encrypted vault (Auth Manager) |
| **Audit trail** | None | Limited | `sub` + `iss` claims | Full agent + user identity |
| **Key rotation** | N/A | Manual | Key pair regeneration | Automatic (24h) |
| **Scope control** | None | None | OAuth scopes | OAuth scopes + IAM policies |
| **Production ready** | No | No | Demo/staging | Yes |

---

## 7. Step-by-Step Demo

### Prerequisites

```bash
# Install dependencies
UV_INDEX_URL=https://pypi.org/simple uv sync

# Verify GCP access
gcloud auth application-default print-access-token >/dev/null
```

### Local test (stdio, no deployment)

```bash
uv run python src/test_mcp_local.py
```

This spawns the MCP server as a subprocess, creates an ADK agent with `McpToolset`, and runs test queries. No Cloud Run or Agent Engine needed.

### Deploy MCP server to Cloud Run

```bash
# Full pipeline: deploy MCP server + agent + traffic
uv run python src/deploy_mcp_agent.py

# Or deploy MCP server separately first
cd src/mcp_server
gcloud builds submit --tag gcr.io/wortz-project-352116/user-service-mcp
gcloud run deploy user-service-mcp \
    --image gcr.io/wortz-project-352116/user-service-mcp \
    --region us-central1 \
    --allow-unauthenticated \
    --port 8080
```

### Register with Agent Registry

```bash
export MCP_SERVER_URL="https://user-service-mcp-679926387543.us-central1.run.app/mcp"
bash scripts/register_agent_registry.sh
```

### Configure Agent Identity

```bash
export AGENT_ENGINE_ID="reasoningEngines/1234567890"
export MCP_SERVER_URL="https://user-service-mcp-679926387543.us-central1.run.app"
bash scripts/setup_agent_identity.sh
```

### Verify

```bash
# Check agent discovery
gcloud alpha agent-registry services list --project=wortz-project-352116 --location=us-central1

# Check auth connector
gcloud alpha agent-identity connectors list --project=wortz-project-352116 --location=us-central1

# Check Cloud Logging for tool call audit trail
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload:"[update_user_email]"' \
    --project=wortz-project-352116 --limit=5
```

---

## Launch Status Reference

| Feature | Status | Notes |
|---------|--------|-------|
| Agent Identity (GCP services) | **GA** | SPIFFE + X.509 for Google Cloud |
| Agent Identity Connectors | Preview | 2-legged, 3-legged OAuth, API keys |
| Auth Manager | Preview | Encrypted credential vault |
| Agent Registry | Public Preview | MCP server registration + discovery |
| Model Armor for MCP | Preview | `tools/call` screening |
| Agent Gateway | Private Preview | Central policy enforcement |
| VPC Service Controls | Preview | Agent identities in perimeter rules |
| Tool Annotations | **GA** | `destructiveHint`, `readOnlyHint`, etc. |
