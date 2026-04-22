# Agent Engine: Evals and BigQuery Analytics Setup

This repository demonstrates the end-to-end architecture for deploying a Vertex AI Agent Engine solution, evaluating it with a custom rubric, and pushing the evaluation metrics into BigQuery for visual reporting using Looker or Looker Studio.

## Highlights Included

### 1. Agent Engine Native Metrics (Inside Engine)
When using Vertex AI Agent Engine (`ReasoningEngine`), the framework automatically emits out-of-the-box system telemetry:
*   **Agent Traces:** Every interaction step, thought, tool execution, and observation is natively captured and emitted via OpenTelemetry.
*   **Latency & Tokens:** API request latency, input tokens, and output token consumptions are automatically tracked without custom telemetry code. 
*   **Cloud Observability Integration:** These native metrics are automatically observable within Cloud Trace and Cloud Logging.

### 2. Custom Evaluation Rubrics
Instead of relying strictly on naive metrics like BLEU or exact match, we use the `vertexai.evaluation` service to deploy **Model-as-a-Judge** scoring:
*   **Custom Pointwise Metrics:** See `src/evaluate_and_export.py` for an example of `PointwiseMetricPromptTemplate` where you define qualitative behavior rubrics (e.g., "helpfulness", "conciseness").
*   The Vertex Eval service parses sample prompts+responses and generates a numeric score mapping across your defined rubric (1 to 5).

### 3. Evaluating and Pushing BigQuery Extentions
To monitor longitudinal agent quality over time inside Looker:
*   The `EvalTask` executes against a test dataset and returns a Pandas DataFrame containing the result payloads (`metrics_table`).
*   The script automatically appends current execution timestamps and pushes the data to a specified BigQuery Dataset using `pandas-gbq`.
*   You can then attach Looker to this BigQuery table to track your Agent's average quality score mapped across specific releases.

## Getting Started

Following standard project guidelines, use `uv` for dependency management:

### 1. Setup Environment

```bash
cd agent_engine_eval_demo
# Install dependencies from pyproject.toml using public PyPI index if needed
UV_INDEX_URL=https://pypi.org/simple uv sync
```

### 2. Configure Environment Variables

Create an `opentelemetry.env` file in the root directory with the following variables to enable detailed OTel tracing:

```env
GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true
OTEL_SERVICE_NAME=demo-finance-agent
OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
```

### 3. Local Testing

Before deploying, you can test the agent locally to verify model access and basic functionality:

```bash
uv run python src/test_locally.py
```

### 4. Deploy and Evaluate

To deploy the agent to Vertex AI Agent Engine, generate traffic, run evaluations, and export results to BigQuery all in one go:

```bash
uv run python src/deploy_agent.py
```

*Note: This script requires a staging bucket in Google Cloud Storage. Ensure it is configured correctly in the script.*
