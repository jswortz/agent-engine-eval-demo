# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Two architecture patterns for agent evaluation on Vertex AI Agent Engine:

- **Pattern 1: Cloud Run** — Custom Model-as-a-Judge rubrics with `EvalTask`, manual BigQuery export via `pandas-gbq`. See `docs/pattern1_cloud_run.md`.
- **Pattern 2: Agent Runtime** — ADK agents with native OTEL (`AdkApp(enable_tracing=True)`), Online Monitors (automated 10-min eval cycle), Cloud Logging sink to BigQuery. See `docs/pattern2_agent_runtime.md`.

The agent is a simple finance/billing assistant (`FinanceAgent`) used to demonstrate both patterns.

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
```

## Architecture

### Pattern 1: Cloud Run
1. Deploy `ReasoningEngine` agent with OTEL env vars
2. Generate traffic, collect prompt-response pairs
3. Run custom `EvalTask` with `PointwiseMetric` rubric (helpfulness + conciseness, 1-5 scale)
4. Export scores to BigQuery via `pandas-gbq`

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
- `docs/assets/generated/` — Paperbanana-generated architecture diagrams (end-to-end, OTEL tracing, eval pipeline, online monitor loop)

## Gotchas

- `deploy_agent.py` uses the ADK `Agent` + `AdkApp` pattern with `vertexai.Client` API. `agent.py` is an older template with `set_up()`/`query()` methods — the deploy script is authoritative.
- Column names from Vertex Eval contain `/` characters — scripts clean these with `replace('/', '_')` before BigQuery export.
- Online monitor results land in Cloud Logging immediately but the Console Evaluation tab reads from Cloud Monitoring, which may lag by several evaluator cycles.
- Only 4 predefined metrics exist for online monitors: `final_response_quality_v1`, `hallucination_v1`, `safety_v1`, `tool_use_quality_v1`.
