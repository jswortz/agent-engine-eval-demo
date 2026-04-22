import pandas as pd
import pandas_gbq
import vertexai
from vertexai.preview import reasoning_engines
from vertexai.evaluation import EvalTask, PointwiseMetric, PointwiseMetricPromptTemplate

PROJECT = "wortz-project-352116"
LOCATION = "us-central1"
BQ_DATASET = "agent_metrics"
BQ_TABLE = "eval_rubric_results"

vertexai.init(project=PROJECT, location=LOCATION, staging_bucket="gs://wortz-project-352116-vertex-staging-us-central1")

# =====================================================================
# 0. Define Agent Inline
# =====================================================================
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

# =====================================================================
# 1. Deploy Agent
# =====================================================================
print("Deploying FinanceAgent to Vertex AI Agent Engine...")
engine = reasoning_engines.ReasoningEngine.create(
    FinanceAgent(project=PROJECT, location=LOCATION),
    requirements=["google-cloud-aiplatform", "google-cloud-bigquery", "pandas"],
    display_name="Demo Finance Agent Real"
)

print(f"Agent deployed successfully. Resource Name: {engine.resource_name}")

# =====================================================================
# 2. Generate Traffic (Query Agent)
# =====================================================================
print("\nGenerating traffic by querying the deployed agent...")
prompts = [
    "What is the status of billing account A100?",
    "How do I open a support ticket for GCP?"
]

references = [
    "Billing account A100 is Active.",
    "Go to the Cloud Console to open a support ticket."
]

responses = []
for prompt in prompts:
    print(f"Querying agent with: '{prompt}'")
    response = engine.query(prompt=prompt)
    print(f"Agent response: '{response}'")
    responses.append(response)

eval_dataset = pd.DataFrame({
    "prompt": prompts,
    "response": responses,
    "reference": references
})

# =====================================================================
# 3. Run Evaluation
# =====================================================================
print("\nInitiating Vertex AI EvalTask with Custom Rubric...")
custom_helpfulness_metric = PointwiseMetric(
    metric="agent_quality_score",
    metric_prompt_template=PointwiseMetricPromptTemplate(
        criteria={
            "helpfulness": "The response must directly and accurately answer the request.",
            "concisiseness": "The response must be brief."
        },
        rating_rubric={"1": "Fail", "3": "Passable", "5": "Perfect"}
    )
)

eval_task = EvalTask(
    dataset=eval_dataset,
    metrics=["exact_match", custom_helpfulness_metric],
    experiment="agent-eval-looker-experiment"
)

eval_result = eval_task.evaluate()
metrics_df = eval_result.metrics_table
metrics_df.columns = [c.replace('/', '_') for c in metrics_df.columns]

# Add metadata
metrics_df["eval_timestamp"] = pd.Timestamp.utcnow()
metrics_df["agent_version"] = "v1.0.0"

print("\n[Summary Metrics]")
print(eval_result.summary_metrics)

# =====================================================================
# 4. Export to BigQuery
# =====================================================================
destination_table = f"{BQ_DATASET}.{BQ_TABLE}"
print(f"\nPushing telemetry data to BigQuery: {PROJECT}.{destination_table}")

try:
    pandas_gbq.to_gbq(
        metrics_df,
        destination_table=destination_table,
        project_id=PROJECT,
        if_exists="append"
    )
    print("Export completed successfully. Data is now available for Looker dashboards.")
except Exception as e:
    print(f"Failed to push to BigQuery: {e}")
