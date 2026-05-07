# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Three architecture patterns for agent evaluation and deployment on Vertex AI Agent Engine:

- **Pattern 1: Cloud Run** — Custom Model-as-a-Judge rubrics with `EvalTask`, manual BigQuery export via `pandas-gbq`. See `docs/pattern1_cloud_run.md`.
- **Pattern 2: Agent Runtime** — ADK agents with native OTEL (`AdkApp(enable_tracing=True)`), Online Monitors (automated 10-min eval cycle), Cloud Logging sink to BigQuery. See `docs/pattern2_agent_runtime.md`.
- **Pattern 3: BYO MCP** — Bring Your Own MCP server with JWT OAuth authentication, Agent Identity integration, and Model Armor protection. See `docs/pattern3_byo_mcp.md`.

Patterns 1-2 use a simple finance/billing assistant (`FinanceAgent`). Pattern 3 uses a user management agent backed by a BYO MCP server with a mock user database.

## Commands

```bash
# Install dependencies (use public PyPI if needed)
UV_INDEX_URL=https://pypi.org/simple uv sync

# Test agent locally (verifies model access)
uv run python src/test_locally.py

# Deploy agent to Agent Engine + generate traffic + run evals + export to BigQuery
uv run python src/deploy_agent.py

# Run evaluation and BigQuery export standalone
uv run python src/evaluate_and_export.py

# Tests
uv run pytest tests/

# Online monitor CRUD & testing
python src/manage_online_monitors.py list
python src/manage_online_monitors.py test
python src/manage_online_monitors.py get <evaluator_id>
python src/manage_online_monitors.py create
python src/manage_online_monitors.py pause <evaluator_id>
python src/manage_online_monitors.py resume <evaluator_id>
python src/manage_online_monitors.py delete <evaluator_id>

# Verify online monitors are working (checks evaluator, traces, logging, monitoring)
python src/verify_online_monitors.py

# --- Pattern 3: BYO MCP ---

# Test MCP agent locally (stdio, no deployment needed)
uv run python src/test_mcp_local.py

# Deploy MCP server to Cloud Run + agent to Agent Engine + generate traffic
uv run python src/deploy_mcp_agent.py

# Deploy agent only (MCP server already deployed)
uv run python src/deploy_mcp_agent.py --mcp-url https://user-service-mcp-HASH.run.app/mcp

# Register MCP server with Agent Registry
export MCP_SERVER_URL="https://user-service-mcp-HASH.run.app/mcp"
bash scripts/register_agent_registry.sh

# Set up Agent Identity connectors
export AGENT_ENGINE_ID="reasoningEngines/1234567890"
bash scripts/setup_agent_identity.sh
```

## Architecture

### Pattern 1: Cloud Run
1. Deploy `ReasoningEngine` agent with OTEL env vars
2. Generate traffic, collect prompt-response pairs
3. Run custom `EvalTask` with `PointwiseMetric` rubric (helpfulness + conciseness, 1-5 scale)
4. Export scores to BigQuery via `pandas-gbq`

### Pattern 3: BYO MCP
1. Deploy FastMCP server to Cloud Run with JWT auth (`JWTVerifier`) protecting a mock user DB
2. Deploy ADK agent with `McpToolset` using `StreamableHTTPConnectionParams` + Bearer token
3. Register MCP server with Agent Registry (tool annotations: `destructiveHint`, `readOnlyHint`)
4. Configure Agent Identity connectors (2-legged OAuth) + bind to agent
5. Model Armor screens `tools/call` requests and responses for prompt injection

### Pattern 2: Agent Runtime (current focus)
1. Deploy ADK `Agent` via `AdkApp(enable_tracing=True)` with `vertexai.Client` API
2. OTEL auto-instruments all spans with `gen_ai.*` semantic conventions
3. Online Monitors evaluate traces every 10 minutes with 4 predefined metrics (0.0-1.0)
4. Results flow: Cloud Logging → BigQuery (via log sink `online-eval-to-bq`)

Critical env vars for Pattern 2 online evaluation:
- `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`
- `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=EVENT_ONLY`

## GCP Configuration

- **Project**: `wortz-project-352116`
- **Region**: `us-central1`
- **Model**: `gemini-2.5-flash` (see `gemini.md` for model compatibility notes)
- **Staging bucket**: `gs://wortz-project-352116-vertex-staging-us-central1`
- **BigQuery (offline evals)**: `agent_metrics.eval_rubric_results`
- **BigQuery (online evals)**: `online_eval_results` (via Cloud Logging sink `online-eval-to-bq`)
- **Active agent**: `reasoningEngines/6686359456680247296` (Demo Finance Agent ADK v2)
- **Active monitor**: `onlineEvaluators/5991476354263023616` (Finance Agent Quality Evaluator v2)

## Key Files

- `src/deploy_agent.py` — Full pipeline: deploy + traffic + eval + BQ export (the main script)
- `src/evaluate_and_export.py` — Standalone eval + BQ export with reusable `run_evaluation_and_export_to_bq()` function
- `src/agent.py` — Agent class template (reference; `deploy_agent.py` has its own inline copy with OTel env vars)
- `src/setup_online_evaluators.py` — Creates online evaluators via v1beta1 API
- `src/manage_online_monitors.py` — Full CRUD + integration test for online monitors
- `src/verify_online_monitors.py` — Verifies monitors are active and producing results across all 4 signal layers
- `src/mock_ui.html` — Static HTML dashboard mockup showing trace waterfall and eval metrics
- `gemini.md` — Documents which Gemini model versions work and which return 404/access denied
- `docs/pattern1_cloud_run.md` — Pattern 1: Cloud Run — Custom Evaluation & BigQuery Reporting
- `docs/pattern2_agent_runtime.md` — Pattern 2: Agent Runtime with Native OTEL & Monitors
- `src/mcp_server/server.py` — FastMCP server with JWT auth + mock user DB (3 tools)
- `src/mcp_server/auth.py` — RSA key pair generation + JWT token creation + JWTVerifier config
- `src/mcp_server/mock_db.py` — In-memory user database (5 demo users)
- `src/mcp_agent.py` — ADK agent using McpToolset (stdio local / SSE remote)
- `src/deploy_mcp_agent.py` — Deploy MCP server to Cloud Run + agent to Agent Engine
- `src/test_mcp_local.py` — Local end-to-end test via stdio
- `scripts/register_agent_registry.sh` — Register MCP server with Agent Registry
- `scripts/setup_agent_identity.sh` — Create Agent Identity connectors + bindings
- `scripts/toolspec.json` — MCP tool spec with security annotations
- `docs/pattern3_byo_mcp.md` — Pattern 3: BYO MCP with OAuth + Agent Identity security
- `docs/assets/generated/` — Paperbanana-generated architecture diagrams (end-to-end, OTEL tracing, eval pipeline, online monitor loop)

## Gotchas

- `deploy_agent.py` uses the ADK `Agent` + `AdkApp` pattern with `vertexai.Client` API. `agent.py` is an older template with `set_up()`/`query()` methods — the deploy script is authoritative.
- Column names from Vertex Eval contain `/` characters — scripts clean these with `replace('/', '_')` before BigQuery export.
- Online monitor results land in Cloud Logging immediately but the Console Evaluation tab reads from Cloud Monitoring, which may lag by several evaluator cycles.
- Only 4 predefined metrics exist for online monitors: `final_response_quality_v1`, `hallucination_v1`, `safety_v1`, `tool_use_quality_v1`.
- MCP server auth is only enforced on HTTP transports (Streamable HTTP/SSE). Stdio connections (local dev) bypass auth — no HTTP headers available. This is the intended pattern.
- `SseConnectionParams`/`StreamableHTTPConnectionParams` with static `headers` is picklable (required for Agent Engine deployment). Dynamic `header_provider` callables are NOT picklable — avoid for deployed agents.
- Agent Identity connectors and Agent Registry commands use `gcloud alpha` — APIs may change.
