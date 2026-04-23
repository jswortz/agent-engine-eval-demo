# Agent Engine: Evaluation & Tracing Report — trends2insights

This whitepaper presents the complete evaluation and tracing analysis for the **trends2insights** agent, a multi-tool ADK (Agent Development Kit) agent deployed on [Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/docs/generative-ai/agent-engine). It demonstrates how Agent Engine's native [OpenTelemetry](https://opentelemetry.io/) instrumentation provides deep observability into multi-step reasoning loops, and how [Model-as-a-Judge](https://cloud.google.com/vertex-ai/docs/generative-ai/eval) evaluations surface qualitative insights that are exported to [BigQuery](https://cloud.google.com/bigquery) for longitudinal analysis.

> **Full interactive report:** [`src/whitepaper2_report.html`](../src/whitepaper2_report.html)

---

## 1. Agent Engine Deployment

The trends2insights agent is a production ADK agent that acts as a Chief Marketing Officer, orchestrating real-time Google Search and YouTube trend data to build marketing campaigns.

![Deployment Details](assets/wp2_header_deployment.png)
*Figure 1: Agent Engine deployment metadata — trends2insights (reasoningEngines/8788263399906607104) running gemini-3-flash-preview with OpenTelemetry 1.38.0 auto-instrumentation on Agent Engine.*

| Property | Value |
|:---|:---|
| **Agent Name** | trends2insights |
| **Engine Resource** | `reasoningEngines/8788263399906607104` |
| **Model** | `gemini-3-flash-preview` |
| **Region** | `us-central1` |
| **Framework** | Google ADK (Agent Development Kit) |
| **API Mode** | `stream_query` (streaming) |
| **OTEL** | Enabled (auto-instrumented) |
| **Tools** | `setup_campaign`, `gather_trends`, `select_trend`, `run_research` |

---

## 2. OpenTelemetry Trace Waterfalls

Agent Engine automatically wraps every ADK agent step in OpenTelemetry spans, providing a complete execution timeline without any custom instrumentation code. We sent 4 queries to the agent, producing **34 spans across 4 traces**.

### Trace 1: Simple Query (4 spans, ~4.6s)

A query without campaign context triggers a single LLM call — the agent asks for clarifying information before using tools.

![Trace Waterfall 1](assets/wp2_traces_1.png)
*Figure 2: OTEL trace waterfalls showing Trace 1 (simple query, 4 spans) and Trace 2 (TechVista multi-tool, 10 spans). The span hierarchy shows invocation → invoke_agent → call_llm → generate_content, with tool execution spans (setup_campaign, gather_trends) interleaved in the ReAct loop.*

### Traces 2-4: Multi-Tool Campaigns (10 spans each, ~20s)

When provided with full campaign context (brand, product, audience, selling points), the agent executes a 3-step ReAct loop:

1. **Intent Detection** — LLM recognizes campaign parameters, calls `setup_campaign` tool
2. **Gather Decision** — LLM decides to fetch trends, calls `gather_trends` tool
3. **Present Results** — LLM synthesizes trend data into strategic recommendations

![Trace Waterfall 2](assets/wp2_traces_2.png)
*Figure 3: Detailed span waterfalls for Trace 2 (TechVista) and Trace 3 (CloudNova) showing the complete ReAct loop with token counts per step. The gather_trends tool dominates latency at 10-12s (fetching live Google Search + YouTube API data).*

### Trace Insights

| Metric | Min | Max | Avg |
|:---|:---|:---|:---|
| End-to-End Latency | 4.6s | 25.0s | 17.4s |
| LLM Inference (per call) | 0.3s | 9.4s | 4.0s |
| Tool Execution (`gather_trends`) | 8.8s | 11.8s | 10.2s |
| Input Tokens (full invocation) | 3,006 | 10,753 | 8,793 |
| Output Tokens (full invocation) | 202 | 1,035 | 822 |

**Key Finding:** The `gather_trends` tool dominates latency at 8.8-11.8s (fetching live Google Search + YouTube trending data via external APIs). LLM inference for result presentation averages 8.2s due to large context windows (~4,500 input tokens with full trend tables). The simple query with no tool calls completes in 4.6s, establishing the baseline LLM-only latency.

---

## 3. Model-as-a-Judge Evaluation

We evaluated the agent's responses using Vertex AI's `EvalTask` with a custom `PointwiseMetric` rubric measuring four criteria:

- **Helpfulness** — actionable marketing insights
- **Conciseness** — well-organized, not verbose
- **Tool Usage** — correct use of `setup_campaign`/`gather_trends`
- **Strategic Insight** — brand-trend alignment quality

![Evaluation Scores](assets/wp2_eval_scores.png)
*Figure 4: Model-as-a-Judge evaluation results — mean quality score 2.5/5.0 across 4 evaluations. The agent scored 4.0 on context-gathering behavior but 2.0 on strategic brand-trend alignment due to general (non-domain-specific) trending data.*

### Per-Query Results

| Prompt | Quality | Analysis |
|:---|:---|:---|
| "What are the latest trends?" | **4.0** | Correctly asks clarifying questions before using tools |
| "TechVista: AI analytics for CTOs" | **2.0** | Trends (sports, entertainment) irrelevant to B2B analytics |
| "CloudNova: GPU compute for ML engineers" | **2.0** | Trends not aligned with ML/GPU compute audience |
| "GreenScale: carbon-neutral cloud" | **2.0** | Partially aligned (Earth Day) but missing full trend data |

### Evaluation Analysis

| Issues Identified | What Worked Well |
|:---|:---|
| **Trend Relevance Gap** — General trending topics (sports, entertainment) vs industry-specific trends | **Tool Orchestration** — ReAct loop correctly sequences setup → gather → present |
| **No Domain Filtering** — `gather_trends` returns raw Google Trends without industry filtering | **Context Gathering** — Agent asks clarifying questions when missing info (scored 4.0) |
| **Weak Strategic Alignment** — Only GreenScale + Earth Day showed meaningful alignment | **Persona Consistency** — CMO persona maintained throughout all interactions |

---

## 4. Cross-Version Quality Comparison

All evaluation results are persisted in BigQuery (`agent_metrics.eval_rubric_results`), enabling longitudinal quality tracking across agent versions.

![Cross-Version Comparison](assets/wp2_analysis_versions.png)
*Figure 5: Quality score comparison across 4 agent versions. The v1.x Finance Agent series scored 5.0/5.0 on simple Q&A tasks, while the v2.0.0 trends2insights agent (multi-tool, real-time data) scored 2.5/5.0 — reflecting the harder problem of strategic trend alignment.*

| Version | Agent | Mean Score | Task Complexity |
|:---|:---|:---|:---|
| v1.0.0 | Demo Finance Agent | **5.0 / 5.0** | Simple Q&A (parametric knowledge) |
| v1.1.0-cloudrun | Cloud Run Proxy | **5.0 / 5.0** | Simple Q&A (same agent via HTTP) |
| v1.2.0-otel | OTEL Instrumented | **5.0 / 5.0** | Simple Q&A (with tracing enabled) |
| v2.0.0-trends2insights | ADK Multi-Tool Agent | **2.5 / 5.0** | Multi-step tool orchestration with live data |

The score drop from v1.x to v2.0 is not a regression — it reflects the fundamentally harder problem the trends2insights agent tackles: multi-step tool orchestration with real-time external data requiring strategic interpretation.

---

## 5. BigQuery Evaluation Data Store

![BigQuery Data](assets/wp2_bigquery_data.png)
*Figure 6: Complete BigQuery evaluation data store showing all 16 evaluations across 4 agent versions, ordered by timestamp. Table: `wortz-project-352116.agent_metrics.eval_rubric_results`.*

The BigQuery sink enables:
- **Longitudinal tracking** — Quality trends over time and across versions
- **Regression detection** — Automated alerting when scores drop below thresholds
- **Looker dashboarding** — Dynamic slicing by version, prompt type, and rubric dimension
- **A/B testing** — Comparing agent configurations with statistical significance

---

## 6. OTEL Span Attributes Reference

The following OpenTelemetry span attributes are automatically emitted by Agent Engine for every ADK agent invocation:

| Attribute | Value | Span Type |
|:---|:---|:---|
| `cloud.platform` | `gcp.agent_engine` | All |
| `cloud.resource_id` | `//aiplatform.googleapis.com/.../reasoningEngines/8788263399906607104` | All |
| `service.name` | `8788263399906607104` | All |
| `telemetry.sdk.name` | `opentelemetry` | All |
| `telemetry.sdk.version` | `1.38.0` | All |
| `gen_ai.request.model` | `gemini-3-flash-preview` | GenerateContent |
| `gen_ai.agent.name` | `root_agent` | Agent |
| `gen_ai.usage.input_tokens` | 3,006 - 4,576 | LLM |
| `gen_ai.usage.output_tokens` | 7 - 994 | LLM |
| `gen_ai.tool.type` | `FunctionTool` | Tool |
| `gen_ai.operation.name` | `generate_content` / `execute_tool` | LLM / Tool |
| `user.id` | `eval-user-1` ... `eval-user-4` | GenerateContent |

---

## Conclusion

This report demonstrates the complete observability and evaluation pipeline available on Vertex AI Agent Engine:

1. **Zero-config OTEL tracing** — Agent Engine auto-instruments every ADK agent step (reasoning loops, LLM calls, tool executions) with rich span attributes including token counts, model versions, and tool responses.

2. **Model-as-a-Judge evaluation** — Custom `PointwiseMetric` rubrics translate qualitative agent behavior into trackable numeric scores, surfacing specific improvement areas (in this case: trend data relevance).

3. **BigQuery evaluation sink** — All scores are persisted for longitudinal analysis, enabling cross-version comparison and regression detection via Looker dashboards.

4. **Actionable insights** — The 2.5/5.0 score for trends2insights pinpoints a specific, fixable issue: the `gather_trends` tool needs domain-specific filtering rather than raw Google Trends data. The agent's architecture (ReAct loop, tool orchestration, persona consistency) is sound.

---

*Report generated April 23, 2026 from live Cloud Trace API and BigQuery data.*
*Agent Engine: trends2insights (8788263399906607104) | Project: wortz-project-352116 | Region: us-central1*
