"""Create Online Evaluators for the deployed FinanceAgent on Agent Engine.

These evaluators run every 10 minutes against OTEL traces, scoring them with
predefined metrics. Results appear in the Agent Engine Evaluation tab.
"""

import json
import google.auth
import google.auth.transport.requests

PROJECT_NUMBER = "679926387543"
LOCATION = "us-central1"
AGENT_ENGINE_ID = "6686359456680247296"
AGENT_RESOURCE = f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{AGENT_ENGINE_ID}"

API_BASE = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_NUMBER}/locations/{LOCATION}"

EVALUATOR_CONFIGS = [
    {
        "displayName": "Finance Agent Quality Evaluator",
        "agentResource": AGENT_RESOURCE,
        "metricSources": [
            {"metric": {"predefinedMetricSpec": {"metricSpecName": "final_response_quality_v1"}}},
            {"metric": {"predefinedMetricSpec": {"metricSpecName": "hallucination_v1"}}},
            {"metric": {"predefinedMetricSpec": {"metricSpecName": "safety_v1"}}},
            {"metric": {"predefinedMetricSpec": {"metricSpecName": "tool_use_quality_v1"}}},
        ],
        "config": {"randomSampling": {"percentage": 100}},
        "cloudObservability": {
            "traceScope": {},
            "openTelemetry": {"semconvVersion": "1.39.0"},
        },
    },
]


def get_session():
    import requests
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    })
    return session


def list_evaluators():
    session = get_session()
    resp = session.get(f"{API_BASE}/onlineEvaluators")
    resp.raise_for_status()
    data = resp.json()
    evaluators = data.get("onlineEvaluators", [])
    print(f"Found {len(evaluators)} existing online evaluator(s)")
    for ev in evaluators:
        print(f"  - {ev.get('displayName', 'unnamed')} | state: {ev.get('state', 'unknown')} | {ev.get('name', '')}")
        if ev.get("stateDetails"):
            for detail in ev["stateDetails"]:
                print(f"    state detail: {detail.get('message', '')}")
    return evaluators


def create_evaluator(config):
    session = get_session()
    metrics = [ms["metric"]["predefinedMetricSpec"]["metricSpecName"] for ms in config["metricSources"]]
    print(f"Creating '{config['displayName']}' with metrics: {metrics}")

    resp = session.post(f"{API_BASE}/onlineEvaluators", json=config)

    if resp.status_code == 200:
        result = resp.json()
        op_name = result.get("name", "")
        print(f"  Operation started: {op_name}")
        return result
    else:
        print(f"  Error {resp.status_code}: {resp.text}")
        return None


if __name__ == "__main__":
    print("=== Existing Online Evaluators ===")
    existing = list_evaluators()

    if existing:
        print("\nEvaluators already exist. Skipping creation.")
    else:
        print("\n=== Creating Online Evaluators ===")
        for config in EVALUATOR_CONFIGS:
            create_evaluator(config)

    print("\n=== Final State ===")
    list_evaluators()
