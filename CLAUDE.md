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

1. **Agent definition** (`src/agent.py`) — `FinanceAgent` class with `set_up()` and `query()` methods, deployed as a `ReasoningEngine` on Vertex AI Agent Engine.
2. **Traffic generation** — Queries the deployed agent with test prompts, collects responses.
3. **Evaluation** (`src/evaluate_and_export.py`) — Uses `vertexai.evaluation.EvalTask` with a custom `PointwiseMetric` rubric (helpfulness + conciseness, scored 1-5) plus `exact_match` baseline.
4. **BigQuery export** — Appends scored `metrics_table` DataFrame to `agent_metrics.eval_rubric_results` via `pandas-gbq`.

OpenTelemetry tracing is enabled automatically by Agent Engine when `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true` (set in `opentelemetry.env` and programmatically in `deploy_agent.py`). Traces appear in Cloud Trace without custom instrumentation code.

## GCP Configuration

- **Project**: `wortz-project-352116`
- **Region**: `us-central1`
- **Model**: `gemini-2.5-flash` (see `gemini.md` for model compatibility notes)
- **Staging bucket**: `gs://wortz-project-352116-vertex-staging-us-central1`
- **BigQuery destination**: `agent_metrics.eval_rubric_results`

## Key Files

- `src/deploy_agent.py` — Full pipeline: deploy + traffic + eval + BQ export (the main script)
- `src/evaluate_and_export.py` — Standalone eval + BQ export with reusable `run_evaluation_and_export_to_bq()` function
- `src/agent.py` — Agent class template (reference; `deploy_agent.py` has its own inline copy with OTel env vars)
- `src/setup_online_evaluators.py` — Creates online evaluators via v1beta1 API
- `src/manage_online_monitors.py` — Full CRUD + integration test for online monitors
- `src/verify_online_monitors.py` — Verifies monitors are active and producing results across all 4 signal layers
- `src/mock_ui.html` — Static HTML dashboard mockup showing trace waterfall and eval metrics
- `gemini.md` — Documents which Gemini model versions work and which return 404/access denied
- `docs/reporting_whitepaper.md` — Whitepaper explaining the OTel + eval + Looker architecture

## Gotchas

- `deploy_agent.py` and `agent.py` each define their own `FinanceAgent` class — the `deploy_agent.py` version is the one that actually gets deployed (it includes OTel env var setup in `set_up()`).
- `agent.py` still references `gemini-1.5-pro-preview-0409` while `deploy_agent.py` uses the working model `gemini-2.5-flash`. The deploy script is authoritative.
- Column names from Vertex Eval contain `/` characters — both scripts clean these with `replace('/', '_')` before BigQuery export.
