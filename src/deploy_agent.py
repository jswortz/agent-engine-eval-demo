"""Deploy an ADK FinanceAgent to Vertex AI Agent Engine with OTEL tracing."""

import pandas as pd
import pandas_gbq
import vertexai
from vertexai.evaluation import EvalTask, PointwiseMetric, PointwiseMetricPromptTemplate

PROJECT = "wortz-project-352116"
PROJECT_NUMBER = "679926387543"
LOCATION = "us-central1"
STAGING_BUCKET = "gs://wortz-project-352116-vertex-staging-us-central1"
BQ_DATASET = "agent_metrics"
BQ_TABLE = "eval_rubric_results"


def get_billing_status(account_id: str) -> str:
    """Gets the current status of a Google Cloud billing account.

    Args:
        account_id: The billing account identifier (e.g. 'A100', 'B200').

    Returns:
        The status string for the account.
    """
    statuses = {"A100": "Active", "B200": "Suspended", "C300": "Closed"}
    return statuses.get(account_id, f"Unknown account: {account_id}")


def get_billing_forecast(account_id: str, months: int = 3) -> str:
    """Gets a billing forecast for a Google Cloud account.

    Args:
        account_id: The billing account identifier.
        months: Number of months to forecast (default 3).

    Returns:
        A forecast summary string.
    """
    forecasts = {
        "A100": {"monthly_avg": 12500, "trend": "increasing 8% MoM"},
        "B200": {"monthly_avg": 0, "trend": "suspended"},
        "C300": {"monthly_avg": 0, "trend": "closed"},
    }
    info = forecasts.get(account_id)
    if not info:
        return f"No forecast data for account {account_id}"
    projected = info["monthly_avg"] * months
    return f"Account {account_id}: ${info['monthly_avg']}/mo avg, trend: {info['trend']}, {months}-month projection: ${projected}"


def deploy_agent():
    from google.adk.agents import Agent
    from vertexai.agent_engines import AdkApp

    client = vertexai.Client(project=PROJECT, location=LOCATION)

    agent = Agent(
        model="gemini-2.0-flash",
        name="finance_agent",
        instruction="You are a helpful finance agent focused on Google Cloud billing. "
        "Use the available tools to look up billing account status and forecasts. "
        "Always provide clear, concise answers about billing questions.",
        tools=[get_billing_status, get_billing_forecast],
    )

    app = AdkApp(agent=agent, enable_tracing=True)

    print("Deploying ADK FinanceAgent to Vertex AI Agent Engine...")
    engine = client.agent_engines.create(
        agent=app,
        config={
            "display_name": "Demo Finance Agent ADK",
            "staging_bucket": STAGING_BUCKET,
            "agent_framework": "google-adk",
            "requirements": [
                "google-cloud-aiplatform[adk,agent_engines]",
                "google-adk",
                "opentelemetry-api",
                "opentelemetry-sdk",
                "opentelemetry-instrumentation-fastapi",
                "opentelemetry-instrumentation-grpc",
                "opentelemetry-instrumentation-httpx",
                "opentelemetry-instrumentation-google-genai",
                "opentelemetry-exporter-gcp-logging",
                "opentelemetry-exporter-otlp-proto-http",
            ],
            "env_vars": {
                "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
                "OTEL_SERVICE_NAME": "demo-finance-agent",
                "OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED": "true",
                "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
                "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
            },
        },
    )
    resource_name = engine.api_resource.name
    print(f"Agent deployed. Resource Name: {resource_name}")
    return resource_name


def generate_traffic(resource_name):
    import requests as req
    import google.auth
    import google.auth.transport.requests
    import json

    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)

    engine_id = resource_name.split("/")[-1]
    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}/reasoningEngines/{engine_id}:streamQuery"

    prompts = [
        "What is the status of billing account A100?",
        "How do I open a support ticket for GCP?",
        "What are my current GCP costs this month?",
        "How do I set up a budget alert?",
        "What is the billing forecast for account A100 over the next 6 months?",
    ]
    references = [
        "Billing account A100 is Active.",
        "Go to the Cloud Console to open a support ticket.",
        "Check the Billing section of the Cloud Console for current costs.",
        "Go to Billing > Budgets & alerts to create a budget alert.",
        "Account A100 averages $12,500/month with an increasing trend.",
    ]
    responses = []
    for i, prompt in enumerate(prompts):
        print(f"Querying: '{prompt}'")
        resp = req.post(url,
            headers={"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"},
            json={"input": {"user_id": f"eval-user-{i+1}", "message": prompt}},
            timeout=60,
        )
        texts = []
        for line in resp.text.strip().split("\n"):
            try:
                event = json.loads(line)
                for part in event.get("content", {}).get("parts", []):
                    if "text" in part:
                        texts.append(part["text"])
            except (json.JSONDecodeError, KeyError):
                pass
        response_text = " ".join(texts) if texts else "No response"
        print(f"Response: '{response_text[:120]}...'")
        responses.append(response_text)
    return prompts, responses, references


def run_evaluation(prompts, responses, references):
    vertexai.init(project=PROJECT, location=LOCATION)
    custom_metric = PointwiseMetric(
        metric="agent_quality_score",
        metric_prompt_template=PointwiseMetricPromptTemplate(
            criteria={
                "helpfulness": "The response must directly and accurately answer the request.",
                "conciseness": "The response must be brief.",
            },
            rating_rubric={"1": "Fail", "3": "Passable", "5": "Perfect"},
        ),
    )
    dataset = pd.DataFrame({
        "prompt": prompts,
        "response": responses,
        "reference": references,
    })
    task = EvalTask(
        dataset=dataset,
        metrics=["exact_match", custom_metric],
        experiment="agent-eval-adk-experiment",
    )
    result = task.evaluate()
    metrics_df = result.metrics_table
    metrics_df.columns = [c.replace("/", "_") for c in metrics_df.columns]
    metrics_df["eval_timestamp"] = pd.Timestamp.utcnow()
    metrics_df["agent_version"] = "v2.0.0-adk"

    print("\n[Summary Metrics]")
    print(result.summary_metrics)

    destination_table = f"{BQ_DATASET}.{BQ_TABLE}"
    print(f"\nExporting to BigQuery: {PROJECT}.{destination_table}")
    pandas_gbq.to_gbq(
        metrics_df,
        destination_table=destination_table,
        project_id=PROJECT,
        if_exists="append",
    )
    print("Export completed.")
    return result.summary_metrics


if __name__ == "__main__":
    resource_name = deploy_agent()
    print(f"\nAGENT_ENGINE_RESOURCE_NAME={resource_name}\n")
    prompts, responses, references = generate_traffic(resource_name)
    run_evaluation(prompts, responses, references)
