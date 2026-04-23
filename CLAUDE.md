# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A demo showing the end-to-end workflow for deploying a Vertex AI Agent Engine agent, evaluating it with custom Model-as-a-Judge rubrics, and exporting eval metrics to BigQuery for Looker dashboarding. The agent is a simple finance/billing assistant (`FinanceAgent`).

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

The pipeline has four stages, all orchestrated in `src/deploy_agent.py`:

1. **Agent definition** — ADK agent with `google.adk.agents.Agent`, deployed via `vertexai.agent_engines.AdkApp(enable_tracing=True)`.
2. **Traffic generation** — Queries the deployed agent via `streamQuery` REST API, collects responses.
3. **Offline evaluation** (`src/evaluate_and_export.py`) — Uses `vertexai.evaluation.EvalTask` with a custom `PointwiseMetric` rubric (helpfulness + conciseness, scored 1-5) plus `exact_match` baseline. Results → BigQuery (`agent_metrics.eval_rubric_results`).
4. **Online monitors** — Continuous evaluation via v1beta1 `onlineEvaluators` API. Runs every 10 minutes against OTEL traces, scoring with 4 predefined metrics. Results → Cloud Logging → BigQuery (`online_eval_results` via log sink `online-eval-to-bq`).

OpenTelemetry tracing is enabled automatically by Agent Engine. Critical env vars for online evaluation:
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
- `docs/trends2insights_whitepaper.md` — Whitepaper 2: Agent Engine evaluation & tracing report with online monitors
- `docs/reporting_whitepaper.md` — Whitepaper 1: OTel + eval + Looker architecture (Cloud Run approach)
- `docs/assets/generated/` — Paperbanana-generated architecture diagrams (end-to-end, OTEL tracing, eval pipeline, online monitor loop)

## Gotchas

- `deploy_agent.py` uses the ADK `Agent` + `AdkApp` pattern with `vertexai.Client` API. `agent.py` is an older template with `set_up()`/`query()` methods — the deploy script is authoritative.
- Column names from Vertex Eval contain `/` characters — scripts clean these with `replace('/', '_')` before BigQuery export.
- Online monitor results land in Cloud Logging immediately but the Console Evaluation tab reads from Cloud Monitoring, which may lag by several evaluator cycles.
- Only 4 predefined metrics exist for online monitors: `final_response_quality_v1`, `hallucination_v1`, `safety_v1`, `tool_use_quality_v1`.
