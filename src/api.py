import os
import pandas as pd
import pandas_gbq
import vertexai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from vertexai.preview import reasoning_engines
from vertexai.evaluation import EvalTask, PointwiseMetric, PointwiseMetricPromptTemplate

PROJECT_ID = os.environ.get("PROJECT_ID", "wortz-project-352116")
LOCATION = os.environ.get("LOCATION", "us-central1")
AGENT_ENGINE_RESOURCE_NAME = os.environ.get("AGENT_ENGINE_RESOURCE_NAME", "")
BQ_DATASET = os.environ.get("BQ_DATASET", "agent_metrics")
BQ_TABLE = os.environ.get("BQ_TABLE", "eval_rubric_results")

app = FastAPI(title="Agent Engine Eval Demo")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        _engine = reasoning_engines.ReasoningEngine(AGENT_ENGINE_RESOURCE_NAME)
    return _engine


class QueryRequest(BaseModel):
    prompt: str


class EvalRequest(BaseModel):
    prompts: list[str] = [
        "What is the status of billing account A100?",
        "How do I open a support ticket for GCP?",
    ]
    references: list[str] = [
        "Billing account A100 is Active.",
        "Go to the Cloud Console to open a support ticket.",
    ]
    agent_version: str = "v1.0.0"


@app.get("/health")
def health():
    return {
        "status": "ok",
        "project": PROJECT_ID,
        "location": LOCATION,
        "agent_engine": AGENT_ENGINE_RESOURCE_NAME,
    }


@app.post("/query")
def query(request: QueryRequest):
    engine = get_engine()
    response = engine.query(prompt=request.prompt)
    return {"prompt": request.prompt, "response": response}


@app.post("/evaluate")
def evaluate(request: EvalRequest):
    engine = get_engine()

    responses = []
    for prompt in request.prompts:
        resp = engine.query(prompt=prompt)
        responses.append(resp)

    eval_dataset = pd.DataFrame({
        "prompt": request.prompts,
        "response": responses,
        "reference": request.references,
    })

    vertexai.init(project=PROJECT_ID, location=LOCATION)

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

    eval_task = EvalTask(
        dataset=eval_dataset,
        metrics=["exact_match", custom_metric],
        experiment="agent-eval-cloudrun-experiment",
    )
    eval_result = eval_task.evaluate()
    metrics_df = eval_result.metrics_table
    metrics_df.columns = [c.replace("/", "_") for c in metrics_df.columns]
    metrics_df["eval_timestamp"] = pd.Timestamp.utcnow()
    metrics_df["agent_version"] = request.agent_version

    destination_table = f"{BQ_DATASET}.{BQ_TABLE}"
    pandas_gbq.to_gbq(
        metrics_df,
        destination_table=destination_table,
        project_id=PROJECT_ID,
        if_exists="append",
    )

    return {
        "summary_metrics": eval_result.summary_metrics,
        "rows_exported": len(metrics_df),
        "destination": f"{PROJECT_ID}.{destination_table}",
    }
