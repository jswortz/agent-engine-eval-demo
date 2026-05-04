# POV: Enabling Agent Runtime Observability

This document is a code-first guide to enabling full observability for ADK agents deployed on [Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime). It covers what you need to set, why each setting matters, and what you get in return — from zero-config tracing through to advanced custom instrumentation.

> **Source code reference:** [`src/deploy_agent.py`](../src/deploy_agent.py) contains the complete working implementation.
>
> **Official docs:** [Instrument ADK with OpenTelemetry](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk), [Cloud Trace for ADK](https://adk.dev/integrations/cloud-trace/)

---

![Observability Stack](assets/generated/observability_stack.png)

*Figure 1: Agent Runtime observability stack — auto-instrumented OTEL spans flow through Cloud Trace, Cloud Logging, and Cloud Monitoring into the unified Agent Console dashboard.*

---

## 1. The Minimum Viable Configuration

To enable observability on Agent Runtime, you need exactly **two things**: the `enable_tracing=True` flag and a set of environment variables.

### Code: Deploy with Tracing

```python
from google.adk.agents import Agent
from vertexai.agent_engines import AdkApp
import vertexai

agent = Agent(
    model="gemini-2.0-flash",
    name="finance_agent",
    instruction="You are a helpful finance agent...",
    tools=[get_billing_status, get_billing_forecast],
)

# Step 1: Enable tracing in the ADK app wrapper
app = AdkApp(agent=agent, enable_tracing=True)

# Step 2: Deploy with telemetry environment variables
client = vertexai.Client(project="your-project", location="us-central1")
engine = client.agent_engines.create(
    agent=app,
    config={
        "agent_framework": "google-adk",
        "env_vars": {
            # Required: enables the OTEL telemetry pipeline in Agent Runtime
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",

            # Required: names your service in Cloud Trace spans
            "OTEL_SERVICE_NAME": "demo-finance-agent",

            # Required for Online Monitors: enables gen_ai.* semantic conventions
            "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",

            # Required for Online Monitors: captures prompt/response as trace events
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
        },
    },
)
```

*Source: [Instrument ADK — Configure your ADK environment](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk#configure)*

---

## 2. What Each Environment Variable Does

| Variable | Required For | What It Does | What Happens Without It |
|:---|:---|:---|:---|
| `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY` | All telemetry | Activates the OTEL pipeline in Agent Runtime; exports spans, logs, and metrics to Google Cloud Observability | No telemetry data is collected or exported |
| `OTEL_SERVICE_NAME` | All telemetry | Sets the `service.name` resource attribute on all spans — appears in Cloud Trace as the service identifier | Spans get a generic service name |
| `OTEL_SEMCONV_STABILITY_OPT_IN` | Online Monitors | Enables `gen_ai_latest_experimental` semantic conventions (v1.38.0+), which produce `gen_ai.client.inference.operation.details` events containing message content | Traces have span-level attributes but no message content — Online Monitors cannot score them |
| `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | Online Monitors | When set to `EVENT_ONLY`, attaches prompt/response content as trace events (`gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.definitions`) | Evaluators cannot access message content; they fail silently or produce no results |
| `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED` | Enhanced logging | Auto-instruments Python logging to include trace context (trace ID, span ID) in log entries | Logs and traces are not correlated |
| `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS` | PII protection | When `false`, prevents ADK from attaching message content as span attributes (which have size limits and PII exposure risk) | Content may be duplicated in both span attributes and events; risk of exceeding attribute size limits |

**Critical warning from official docs:**
> Do not set `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` to `true`. When using the most recent semantic conventions, setting the value to `true` results in an invalid configuration and log/trace data is not collected.

*Source: [Instrument ADK — Configure](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk#configure)*

---

## 3. What You Get: Auto-Instrumented Telemetry

Once deployed with the configuration above, Agent Runtime automatically produces three categories of telemetry data with **zero additional code**.

### 3a. Cloud Trace Spans

Every agent invocation generates a trace with nested spans following the ADK execution DAG:

```
invocation                                     (root span, ~4s)
├── invoke_agent finance_agent                 (agent orchestration)
│   ├── call_llm                               (LLM reasoning step)
│   │   └── generate_content gemini-2.0-flash  (model inference, ~3.5s)
│   ├── execute_tool get_billing_status        (tool call, <100ms)
│   ├── call_llm                               (follow-up reasoning)
│   │   └── generate_content gemini-2.0-flash  (model inference)
│   └── execute_tool get_billing_forecast      (tool call, <100ms)
```

Each span carries these resource attributes (auto-injected):

| Attribute | Description | Example |
|:---|:---|:---|
| `cloud.platform` | Runtime platform | `gcp.agent_engine` |
| `cloud.provider` | Cloud provider | `gcp` |
| `cloud.account.id` | GCP project ID | `wortz-project-352116` |
| `cloud.region` | Deployment region | `us-central1` |
| `cloud.resource_id` | Full Agent Engine resource path | `//aiplatform.googleapis.com/.../reasoningEngines/668...` |
| `service.name` | Value of `OTEL_SERVICE_NAME` | `demo-finance-agent` |
| `service.instance.id` | Container instance identifier | `a1aa6130767b...` |
| `telemetry.sdk.name` | SDK producing the spans | `opentelemetry` |
| `telemetry.sdk.version` | OTEL SDK version | `1.38.0` |
| `gen_ai.agent.name` | ADK agent name | `finance_agent` |
| `gen_ai.request.model` | Model used for inference | `gemini-2.0-flash` |
| `gen_ai.conversation.id` | Session/conversation identifier | `6982698593647853568` |

*Source: [Cloud Trace for ADK — Inspect Cloud Traces](https://adk.dev/integrations/cloud-trace/#inspect-cloud-traces)*

### 3b. Cloud Logging

Agent logs automatically route to Cloud Logging with structured payloads:

```
resource.type="aiplatform.googleapis.com/ReasoningEngine"
resource.labels.reasoning_engine_id="6686359456680247296"
```

Log entries include:
- Model request/response payloads (when `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true`)
- HTTP request metadata
- Error details and stack traces
- Trace context (trace ID + span ID) for log-trace correlation

### 3c. Cloud Monitoring Metrics

Agent Runtime exports agent-specific metrics to Cloud Monitoring:

| Metric | Description |
|:---|:---|
| Model call count | Number of LLM inference calls over time |
| Model P95 latency | 95th percentile latency for model inference |
| Tool call count | Number of tool invocations (per tool) |
| Tool P95 duration | 95th percentile duration for tool execution |
| Token usage | Input/output token counts |
| Container CPU/memory | Resource utilization of the agent container |

---

## 4. Console Experience: What You See

The Agent Runtime console provides a purpose-built observability dashboard — this is unique to Agent Runtime and not available on Cloud Run.

### Dashboard Tabs

| Tab | What It Shows |
|:---|:---|
| **Overview** | Session count, invocation count, token usage (input vs output), active model |
| **Models** | Per-model call count, P95 latency, time-series charts |
| **Tools** | Per-tool call count, P95 duration, invocation timeline |
| **Usage** | Container CPU allocation, memory allocation |
| **Logs** | Real-time agent logs (model requests, HTTP responses, payloads) |
| **Traces** | Session list with avg duration, model/tool call counts, token usage per session |
| **Evaluation** | Online Monitor results — time-series charts for quality, hallucination, safety, tool use |

### Trace Detail Views

Each trace can be viewed as:
- **DAG graph** — visual execution flow showing span hierarchy and durations
- **Session conversation** — formatted view with System Message, Input, tool calls, and final response
- **Span detail** — individual span attributes, events (including `gen_ai.input.messages` / `gen_ai.output.messages`), and linked logs
- **Evaluation tab** — per-trace scores from Online Monitors with rubric verdicts and reasoning

---

## 5. Alternative Setup Methods

### 5a. ADK CLI (for local development → cloud deployment)

```bash
# Deploy with tracing enabled via CLI flag
adk deploy agent_engine \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=$GOOGLE_CLOUD_LOCATION \
  --trace_to_cloud \
  ./finance_agent

# Run locally with cloud tracing
adk web --otel_to_cloud
```

*Source: [Cloud Trace for ADK — Using the ADK CLI](https://adk.dev/integrations/cloud-trace/#using-the-adk-cli)*

### 5b. Programmatic Setup (for custom runtimes like FastAPI on Cloud Run)

If you're running the agent on Cloud Run or a custom runtime rather than Agent Runtime, use the ADK telemetry modules directly:

```python
from google.adk import telemetry
from google.adk.telemetry import google_cloud

# Get GCP exporter configuration
hooks = google_cloud.get_gcp_exporters(enable_cloud_tracing=True)

# Initialize and set global OpenTelemetry providers
telemetry.maybe_set_otel_providers(otel_hooks_to_setup=[hooks])
```

This approach requires ADK >= 1.17.0 and produces the same trace data, but you manage the OTEL provider lifecycle yourself.

*Source: [Cloud Trace for ADK — Programmatic Setup](https://adk.dev/integrations/cloud-trace/#programmatic-setup)*

### 5c. OpenTelemetry Packages (manual installation)

For maximum control, install the OTEL packages explicitly:

```bash
pip install 'google-adk>=1.17.0' \
  'opentelemetry-instrumentation-google-genai>=0.4b0' \
  'opentelemetry-instrumentation-sqlite3' \
  'opentelemetry-exporter-gcp-logging' \
  'opentelemetry-exporter-gcp-monitoring' \
  'opentelemetry-exporter-otlp-proto-grpc' \
  'opentelemetry-instrumentation-vertexai>=2.0b0'
```

Then configure the environment variables in an `opentelemetry.env` file:

```bash
OTEL_SERVICE_NAME='demo-finance-agent'
OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED='true'
OTEL_SEMCONV_STABILITY_OPT_IN='gen_ai_latest_experimental'
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT='EVENT_ONLY'
ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS='false'
```

*Source: [Instrument ADK — Install OpenTelemetry packages](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk#install-packages)*

---

## 6. IAM Roles Required

To write telemetry data to Google Cloud Observability services, the agent's service account needs:

| Role | Purpose |
|:---|:---|
| `roles/telemetry.tracesWriter` | Write trace data via the Telemetry (OTLP) API |
| `roles/logging.logWriter` | Write structured logs to Cloud Logging |
| `roles/monitoring.metricWriter` | Write metrics to Cloud Monitoring |
| `roles/aiplatform.user` | Access Vertex AI models |

To **view** telemetry data, users need:

| Role | Purpose |
|:---|:---|
| `roles/cloudtrace.user` | View traces in Trace Explorer |
| `roles/logging.viewer` | View logs in Logs Explorer |
| `roles/monitoring.viewer` | View metrics in Cloud Monitoring |

*Source: [Instrument ADK — Before you begin](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk)*

---

## 7. Verifying Observability Is Working

After deployment, verify telemetry is flowing:

### Check Cloud Trace

```bash
# Via gcloud CLI
gcloud traces list --project=your-project --limit=5

# Or in Console: Trace Explorer → filter by service.name = "demo-finance-agent"
```

### Check Cloud Logging

```bash
gcloud logging read \
  'resource.type="aiplatform.googleapis.com/ReasoningEngine"' \
  --project=your-project --limit=5 --format=json
```

### Check Agent Console

Navigate to: **Console → Agent Platform → Agents → [Your Agent] → Dashboard**

You should see:
- **Overview**: Session count, invocation count, token usage
- **Traces**: Session list with spans
- **Models**: Call count and latency charts
- **Tools**: Per-tool invocation data

### Programmatic Verification

```python
# Use the verify script from this repo
python src/verify_online_monitors.py
```

This checks 4 signal layers: evaluator state, trace presence, logging entries, and monitoring metrics.

---

## 8. Extending Observability

The default ADK instrumentation covers the core agent execution loop. For domain-specific observability, add custom instrumentation:

| Use Case | Approach |
|:---|:---|
| Track resource consumption of agent-invoked tools | Add custom OTEL spans around tool functions |
| Track business rule violations | Emit custom log entries with structured labels |
| Track custom quality scores | Add custom metrics via `opentelemetry-exporter-gcp-monitoring` |
| Capture multimodal data (images, documents) | Set `OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT=jsonl` and `OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK=upload` to record to Cloud Storage |

*Source: [Instrument ADK — Overview](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk), [Collect multimodal prompts and responses](https://docs.cloud.google.com/stackdriver/docs/instrumentation/collect-view-multimodal-prompts-responses)*

---

## References

| Topic | URL |
|:---|:---|
| Instrument ADK with OTEL (Google Cloud Observability) | https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk |
| Cloud Trace for ADK (ADK docs) | https://adk.dev/integrations/cloud-trace/ |
| Agent Runtime observability | https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize |
| Collect multimodal prompts and responses | https://docs.cloud.google.com/stackdriver/docs/instrumentation/collect-view-multimodal-prompts-responses |
| OpenTelemetry GenAI semantic conventions | https://opentelemetry.io/docs/specs/semconv/gen-ai/ |
| Telemetry (OTLP) API | https://docs.cloud.google.com/stackdriver/docs/reference/telemetry/overview |

---

*Document generated May 4, 2026. Based on ADK >= 1.17.0 and Agent Runtime as of this date.*
