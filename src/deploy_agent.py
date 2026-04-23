import pandas as pd
import pandas_gbq
import vertexai
from vertexai.preview import reasoning_engines
from vertexai.evaluation import EvalTask, PointwiseMetric, PointwiseMetricPromptTemplate

PROJECT = "wortz-project-352116"
LOCATION = "us-central1"
STAGING_BUCKET = "gs://wortz-project-352116-vertex-staging-us-central1"
BQ_DATASET = "agent_metrics"
BQ_TABLE = "eval_rubric_results"


# Inline: Agent Engine serializes this class, so it cannot import local modules.
class FinanceAgent:
    def __init__(self, project: str, location: str):
        self.project = project
        self.location = location

    def set_up(self):
        import os
        os.environ["GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"] = "true"
        os.environ["OTEL_SERVICE_NAME"] = "demo-finance-agent"
        os.environ["OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED"] = "true"
        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

        import vertexai
        from vertexai.generative_models import GenerativeModel
        vertexai.init(project=self.project, location=self.location)
        self.model_name = "gemini-2.5-flash"
        self.model = GenerativeModel(self.model_name)
        self.system_prompt = "You are a helpful finance agent focused on Google Cloud billing."

    def query(self, prompt: str) -> str:
        response = self.model.generate_content([self.system_prompt, prompt])
        return response.text


def deploy_agent():
    vertexai.init(project=PROJECT, location=LOCATION, staging_bucket=STAGING_BUCKET)
    print("Deploying FinanceAgent to Vertex AI Agent Engine...")
    engine = reasoning_engines.ReasoningEngine.create(
        FinanceAgent(project=PROJECT, location=LOCATION),
        requirements=[
            "google-cloud-aiplatform",
            "google-cloud-bigquery",
            "pandas",
            "opentelemetry-instrumentation-fastapi",
            "opentelemetry-instrumentation-grpc",
            "opentelemetry-instrumentation-httpx",
            "opentelemetry-instrumentation-google-genai",
            "opentelemetry-exporter-gcp-logging",
            "opentelemetry-exporter-otlp-proto-http",
        ],
        display_name="Demo Finance Agent Real",
    )
    print(f"Agent deployed. Resource Name: {engine.resource_name}")
    return engine.resource_name


def generate_traffic(resource_name):
    engine = reasoning_engines.ReasoningEngine(resource_name)
    prompts = [
        "What is the status of billing account A100?",
        "How do I open a support ticket for GCP?",
    ]
    references = [
        "Billing account A100 is Active.",
        "Go to the Cloud Console to open a support ticket.",
    ]
    responses = []
    for prompt in prompts:
        print(f"Querying: '{prompt}'")
        response = engine.query(prompt=prompt)
        print(f"Response: '{response}'")
        responses.append(response)
    return prompts, responses, references


def run_evaluation(prompts, responses, references):
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
        experiment="agent-eval-looker-experiment",
    )
    result = task.evaluate()
    metrics_df = result.metrics_table
    metrics_df.columns = [c.replace("/", "_") for c in metrics_df.columns]
    metrics_df["eval_timestamp"] = pd.Timestamp.utcnow()
    metrics_df["agent_version"] = "v1.0.0"

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
