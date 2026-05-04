# POV: Cloud Run vs Agent Runtime for Agent Deployment

This document compares two deployment patterns for AI agents on Google Cloud: **Cloud Run** (a general-purpose serverless container platform) and **Agent Runtime** (the purpose-built managed runtime within [Gemini Enterprise Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime)). All claims are sourced from official Google Cloud documentation.

> **Context:** This comparison is written for teams evaluating where to deploy ADK-based agents that need production observability and continuous evaluation. For implementation details, see [Pattern 1: Cloud Run](pattern1_cloud_run.md) and [Pattern 2: Agent Runtime](pattern2_agent_runtime.md).

---

![Cloud Run vs Agent Runtime Comparison](assets/generated/cr_vs_art_comparison.png)

*Figure 1: Side-by-side comparison of Cloud Run and Agent Runtime deployment patterns — infrastructure, observability automation, and platform services.*

---

## Decision Framework

Google Cloud provides a clear decision matrix for choosing an agent runtime:

| Use Case | Recommended Runtime |
|:---|:---|
| Python agent requiring a **fully managed experience** with minimal operational overhead | **Agent Runtime** |
| Containerized application requiring **serverless, event-driven scaling** with language flexibility | **Cloud Run** |
| Containerized application with **complex stateful requirements** and fine-grained infrastructure control | **GKE** |

*Source: [Choose your agentic AI architecture components — Agent runtime](https://docs.cloud.google.com/architecture/choose-agentic-ai-architecture-components#agent_runtime)*

---

## Feature Comparison

### Infrastructure & Operations

| Capability | Cloud Run | Agent Runtime |
|:---|:---|:---|
| **Deployment model** | Container images (any language, any framework) | Python source code with declared dependencies |
| **Language support** | Any language that runs in a container | Python only ([supported frameworks](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime#supported-frameworks)) |
| **Scaling** | Serverless auto-scaling with configurable min/max instances, concurrency, CPU allocation | Fully managed auto-scaling — no configuration required |
| **Infrastructure control** | Full control over container image, runtime, networking, VPC | Abstracted — Google manages all infrastructure |
| **Custom system dependencies** | Full Dockerfile control | Build-time installation scripts for system deps |
| **Deployment artifact** | Container image pushed to Artifact Registry | Python source + `requirements` list uploaded via SDK |
| **Startup time** | Cold start depends on image size; min instances available | Managed by platform |

*Sources: [Cloud Run overview](https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run), [Agent Runtime overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime)*

### Framework Support

Agent Runtime provides tiered integration levels for agent frameworks:

| Integration Level | Frameworks | What It Means |
|:---|:---|:---|
| **Full integration** | ADK, LangChain, LangGraph | Features work across framework, runtime, and Google Cloud ecosystem |
| **SDK integration** | AG2, LlamaIndex | Managed templates per framework in the Agent Platform SDK |
| **Custom template** | CrewAI, custom frameworks | Adapt a custom template to support deployment |

Cloud Run supports **any framework** that can be containerized, with no integration tiers — you bring your own container and handle all framework wiring yourself.

*Source: [Agent Runtime — Supported frameworks](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime#supported-frameworks)*

### Observability

| Capability | Cloud Run | Agent Runtime |
|:---|:---|:---|
| **Tracing** | Manual OTEL instrumentation required; export to Cloud Trace via OTLP exporter | **Auto-instrumented** — `AdkApp(enable_tracing=True)` generates `gen_ai.*` spans automatically |
| **Logging** | Structured logs to stdout/stderr route to Cloud Logging | Same + agent-level structured logs with `gen_ai.*` labels |
| **Monitoring** | Standard Cloud Run metrics (request count, latency, CPU, memory) | Same + **agent-specific metrics** (model calls, tool calls, token usage, P95 latency) |
| **Trace attributes** | Custom — you define your span attributes | Automatic `cloud.platform`, `cloud.resource_id`, `gen_ai.agent.name`, `gen_ai.request.model`, token counts |
| **Console dashboard** | Cloud Run service dashboard | **Agent-specific dashboard** with Overview, Models, Tools, Usage, Logs, Traces, and Evaluation tabs |
| **Topology view** | Not available | Agent relationships visualization showing multi-agent dependencies |

*Sources: [Cloud Trace for ADK](https://adk.dev/integrations/cloud-trace/), [Agent Runtime observability](https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize), [Instrument ADK with OTEL](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk)*

### Evaluation & Quality

| Capability | Cloud Run | Agent Runtime |
|:---|:---|:---|
| **Offline evaluation** | Manual — run `EvalTask` with custom rubrics, export results yourself (e.g., `pandas-gbq` to BigQuery) | Same capability, plus **integrated Gen AI Evaluation service** |
| **Online monitoring** | Not available — must build custom evaluation pipelines | **Built-in Online Monitors** — continuous 10-minute evaluation loop scoring live traces with predefined + custom metrics |
| **Predefined metrics** | None | `final_response_quality_v1`, `hallucination_v1`, `safety_v1`, `tool_use_quality_v1` |
| **Quality alerts** | Manual — set up Cloud Monitoring alerts on custom metrics | **Integrated quality alerts** configurable from the evaluation dashboard |
| **Prompt optimization** | Not available | **Built-in prompt optimization** to improve agent response quality |
| **Simulated evaluation** | Not available | **Simulate agent behavior** against custom criteria |
| **Failure cluster analysis** | Not available | **Analyze evaluation results and failure clusters** |

*Sources: [Online monitoring](https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize/evaluation/evaluate-online), [Agent evaluation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize/evaluation/agent-evaluation), [Optimize overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize)*

### Agent Services (Beyond Compute)

Agent Runtime is not just a compute runtime — it includes a suite of managed services:

| Service | Cloud Run | Agent Runtime |
|:---|:---|:---|
| **Sessions** | Build your own (Firestore, Redis, etc.) | [Agent Platform Sessions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sessions) — managed conversation state |
| **Long-term memory** | Build your own ([Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank) can be used from Cloud Run) | [Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank) — auto-extracts user preferences from conversation history |
| **Code execution sandbox** | Not available natively | [Code Execution](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sandbox/code-execution-overview) — secure, isolated sandbox |
| **Example store** | Not available | [Example Store](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale) (Preview) — dynamic few-shot retrieval |
| **Agent identity** | [Service identity](https://docs.cloud.google.com/run/docs/securing/service-identity) for calling Google Cloud APIs | [Agent identity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-identity) (Preview) — IAM-based agent identity |
| **Agent Gateway** | Not available | [Agent Gateway](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview) (Preview) — rules for agentic communications |
| **Threat detection** | Not available | [Agent Runtime Threat Detection](https://docs.cloud.google.com/security-command-center/docs/agent-engine-threat-detection-overview) (Preview) via Security Command Center |
| **A2A protocol** | Manual implementation | [Agent2Agent](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/create-an-a2a-agent) — built-in support |

*Source: [Gemini Enterprise Agent Platform — Scale](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale)*

### Security & Governance

| Capability | Cloud Run | Agent Runtime |
|:---|:---|:---|
| **VPC-SC** | Supported | Supported |
| **CMEK** | Supported (via KMS) | Supported (via [Secret Manager](https://docs.cloud.google.com/agent-builder/agent-engine/manage/access#cmek)) |
| **IAM** | Standard Cloud Run IAM | Standard IAM + agent-level identity (Preview) |
| **Model Armor** | Integration via [Model Armor API](https://docs.cloud.google.com/model-armor/reference/rest) | Integration via Agent Gateway |
| **Private networking** | VPC connectors, Private Service Connect | [PSC interface](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale) for VPC connectivity |
| **Bidirectional streaming** | WebSockets, SSE, streaming HTTP | [Bidirectional streaming](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale) support |

---

## Pros & Cons Summary

### Cloud Run

**Pros:**
- **Language agnostic** — deploy agents in Python, Go, Java, Node.js, or any containerized language
- **Full infrastructure control** — custom Docker images, networking, VPC, GPU support
- **Mature ecosystem** — extensive documentation, community tooling, third-party integrations (Langfuse, Arize, etc.)
- **Flexible observability** — connect any observability tool, not locked into Google's agent-specific dashboards
- **Cost model** — granular pay-per-request pricing with configurable min instances

**Cons:**
- **No built-in agent evaluation** — must build and maintain custom evaluation pipelines
- **No Online Monitors** — no continuous quality scoring of live traffic
- **Manual OTEL instrumentation** — tracing requires explicit setup for `gen_ai.*` attributes
- **No managed sessions/memory** — must integrate external state management
- **No agent-specific dashboard** — standard Cloud Run metrics only

### Agent Runtime

**Pros:**
- **Zero-config observability** — `enable_tracing=True` auto-instruments all ADK spans with `gen_ai.*` semantic conventions
- **Built-in Online Monitors** — continuous 10-minute evaluation loop with 4 predefined metrics, no custom code needed
- **Agent-specific console** — dedicated dashboard with Models, Tools, Traces, Evaluation tabs
- **Managed agent services** — Sessions, Memory Bank, Code Execution, Example Store, Agent Gateway included
- **Integrated evaluation suite** — offline eval, simulated eval, quality alerts, prompt optimization, failure cluster analysis
- **Security features** — Agent identity, threat detection via SCC, Agent Gateway

**Cons:**
- **Python only** — no support for Go, Java, or other languages
- **Limited framework customization** — must use supported frameworks or write a custom template
- **Less infrastructure control** — cannot customize the container image, networking, or compute resources at the same granularity as Cloud Run
- **Private dependency management** — Cloud Run and GKE offer more direct IAM-based configuration paths for strict security requirements
- **No custom MCP server hosting** — Agent Runtime manages the runtime for MCP components but doesn't support hosting custom MCP servers
- **Preview features** — several capabilities (Agent Gateway, Agent Identity, Threat Detection) are in Preview

---

## When to Use Each Pattern

### Choose Agent Runtime (Pattern 2) when:

1. You're building a **Python ADK agent** and want the fastest path to production observability
2. You need **continuous quality monitoring** without building custom evaluation infrastructure
3. You want **managed conversation state** (Sessions) and **long-term memory** (Memory Bank)
4. Your team is **small or ops-light** and prefers a fully managed experience
5. You need **agent-specific security features** like Agent Gateway and threat detection

### Choose Cloud Run (Pattern 1) when:

1. Your agent is written in a **language other than Python** (Go, Java, Node.js, etc.)
2. You need **full control over the container image** and compute environment
3. You already have **existing observability infrastructure** (Datadog, Langfuse, Arize, etc.)
4. Your organization has **strict private dependency requirements** that need direct IAM-based config
5. You want to deploy **custom MCP servers** alongside your agent
6. You need **GPU-enabled compute** for running fine-tuned models alongside the agent

### Hybrid approach:

You can use Agent Runtime for agent deployment with Online Monitors while still using Cloud Run for custom tooling, MCP servers, or frontend services. Memory Bank can also be [used from Cloud Run](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank) by creating at least one Agent Engine instance.

---

## Code Comparison: Deploying the Same Agent

### Cloud Run Deployment

```python
# Requires: Dockerfile, container build, OTEL setup, custom eval pipeline
from google.adk.agents import Agent
from google.adk.apps import AdkApp

agent = Agent(
    model="gemini-2.0-flash",
    name="finance_agent",
    instruction="You are a helpful finance agent...",
    tools=[get_billing_status, get_billing_forecast],
)
app = AdkApp(agent=agent, enable_tracing=True)

# Deploy: build container, push to Artifact Registry, deploy to Cloud Run
# Observability: configure OTEL exporters, set up Cloud Trace manually
# Evaluation: build custom EvalTask pipeline, export to BigQuery yourself
# Monitoring: no built-in online monitors — build your own or go without
```

### Agent Runtime Deployment

```python
from google.adk.agents import Agent
from vertexai.agent_engines import AdkApp

agent = Agent(
    model="gemini-2.0-flash",
    name="finance_agent",
    instruction="You are a helpful finance agent...",
    tools=[get_billing_status, get_billing_forecast],
)
app = AdkApp(agent=agent, enable_tracing=True)

client = vertexai.Client(project=PROJECT, location=LOCATION)
engine = client.agent_engines.create(
    agent=app,
    config={
        "agent_framework": "google-adk",
        "env_vars": {
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
            "OTEL_SERVICE_NAME": "demo-finance-agent",
            "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
        },
    },
)
# Observability: auto-instrumented — traces appear in Cloud Trace immediately
# Evaluation: create an Online Monitor via Console or API — scores every 10 min
# Dashboard: agent-specific console with Models, Tools, Traces, Evaluation tabs
```

---

## References

All documentation links are from official Google Cloud sources:

| Topic | URL |
|:---|:---|
| Choose agentic AI architecture components | https://docs.cloud.google.com/architecture/choose-agentic-ai-architecture-components |
| Agent Runtime overview | https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime |
| Cloud Run for AI agents | https://docs.cloud.google.com/run/docs/ai-agents |
| Single-agent system on Cloud Run (ADK) | https://docs.cloud.google.com/architecture/single-agent-ai-system-adk-cloud-run |
| Cloud Trace for ADK | https://adk.dev/integrations/cloud-trace/ |
| Instrument ADK with OTEL | https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk |
| Online monitoring | https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize/evaluation/evaluate-online |
| Agent evaluation overview | https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize/evaluation/agent-evaluation |
| Gemini Enterprise Agent Platform — Scale | https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale |
| Gemini Enterprise Agent Platform — Optimize | https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize |

---

*Document generated May 4, 2026. All comparisons based on official Google Cloud documentation as of this date.*
