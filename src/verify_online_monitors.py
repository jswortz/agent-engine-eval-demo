"""Programmatically verify that Online Monitors are running and producing evaluation results.

Checks:
1. Online evaluator exists and is ACTIVE
2. Agent traces exist in Cloud Trace with gen_ai.* spans
3. Evaluation results exist in Cloud Logging
4. Evaluation scores are present in Cloud Monitoring
"""

import json
import sys
from datetime import datetime, timedelta, timezone

import google.auth
import google.auth.transport.requests
import requests

PROJECT = "wortz-project-352116"
PROJECT_NUMBER = "679926387543"
LOCATION = "us-central1"
AGENT_ENGINE_ID = "6686359456680247296"

API_BASE = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_NUMBER}/locations/{LOCATION}"
TRACE_API = f"https://cloudtrace.googleapis.com/v1/projects/{PROJECT}/traces"
LOGGING_API = "https://logging.googleapis.com/v2/entries:list"
MONITORING_API = f"https://monitoring.googleapis.com/v3/projects/{PROJECT}/timeSeries"


def get_auth_headers():
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return {"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"}


def check_evaluator_status(headers):
    print("=" * 60)
    print("CHECK 1: Online Evaluator Status")
    print("=" * 60)

    resp = requests.get(f"{API_BASE}/onlineEvaluators", headers=headers)
    resp.raise_for_status()
    evaluators = resp.json().get("onlineEvaluators", [])

    matching = [e for e in evaluators if AGENT_ENGINE_ID in e.get("agentResource", "")]

    if not matching:
        print(f"  FAIL: No evaluator found for agent {AGENT_ENGINE_ID}")
        return False

    for ev in matching:
        state = ev.get("state", "UNKNOWN")
        name = ev.get("name", "").split("/")[-1]
        display = ev.get("displayName", "")
        metrics = [ms["metric"]["predefinedMetricSpec"]["metricSpecName"]
                    for ms in ev.get("metricSources", [])]
        created = ev.get("createTime", "")

        print(f"  Evaluator: {name}")
        print(f"  Display Name: {display}")
        print(f"  State: {state}")
        print(f"  Created: {created}")
        print(f"  Metrics: {metrics}")

        details = ev.get("stateDetails", [])
        if details:
            print("  State Details:")
            for d in details:
                print(f"    - {d.get('message', json.dumps(d))}")

        if state != "ACTIVE":
            print(f"  FAIL: Evaluator state is {state}, expected ACTIVE")
            return False

    print("  PASS: Evaluator is ACTIVE")
    return True


def check_traces(headers):
    print("\n" + "=" * 60)
    print("CHECK 2: Agent Traces with gen_ai.* Spans")
    print("=" * 60)

    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "startTime": start,
        "endTime": end,
        "pageSize": 5,
        "view": "COMPLETE",
        "filter": "+gen_ai.operation.name:generate_content",
    }
    resp = requests.get(TRACE_API, headers=headers, params=params)
    resp.raise_for_status()
    traces = resp.json().get("traces", [])

    print(f"  Found {len(traces)} traces with gen_ai.operation.name in last 2h")

    if not traces:
        print("  FAIL: No traces found. Send traffic to the agent first.")
        return False

    for i, t in enumerate(traces[:2]):
        spans = t.get("spans", [])
        span_names = [s.get("name", "") for s in spans]
        has_invoke = any("invoke_agent" in n for n in span_names)
        has_tool = any("execute_tool" in n for n in span_names)
        has_llm = any("call_llm" in n for n in span_names)

        print(f"  Trace {i+1}: {len(spans)} spans | invoke_agent={has_invoke} call_llm={has_llm} execute_tool={has_tool}")

        gen_ai_attrs = set()
        for s in spans:
            for k in s.get("labels", {}):
                if k.startswith("gen_ai"):
                    gen_ai_attrs.add(k)

        print(f"    gen_ai attributes: {sorted(gen_ai_attrs)}")

    required = {"gen_ai.agent.name", "gen_ai.request.model", "gen_ai.operation.name"}
    all_attrs = set()
    for t in traces:
        for s in t.get("spans", []):
            for k in s.get("labels", {}):
                if k.startswith("gen_ai"):
                    all_attrs.add(k)

    missing = required - all_attrs
    if missing:
        print(f"  WARN: Missing required attributes: {missing}")
    else:
        print(f"  PASS: All required gen_ai attributes present")

    return True


def check_eval_results_in_logging(headers):
    print("\n" + "=" * 60)
    print("CHECK 3: Evaluation Results in Cloud Logging")
    print("=" * 60)

    body = {
        "resourceNames": [f"projects/{PROJECT}"],
        "filter": (
            f'resource.type="aiplatform.googleapis.com/ReasoningEngine" '
            f'resource.labels.reasoning_engine_id="{AGENT_ENGINE_ID}" '
            f'labels."event.name"="gen_ai.evaluation.result"'
        ),
        "orderBy": "timestamp desc",
        "pageSize": 50,
    }
    resp = requests.post(LOGGING_API, headers=headers, json=body)
    resp.raise_for_status()
    entries = resp.json().get("entries", [])

    print(f"  Found {len(entries)} evaluation result log entries")

    if not entries:
        print("  FAIL: No evaluation results found in Cloud Logging.")
        print("  The evaluator runs every 10 minutes. Wait and try again.")
        return False

    metrics_seen = {}
    for e in entries:
        labels = e.get("labels", {})
        metric = labels.get("gen_ai.evaluation.name", "unknown")
        score = labels.get("gen_ai.evaluation.score.value", "N/A")

        if metric not in metrics_seen:
            metrics_seen[metric] = []
        metrics_seen[metric].append(float(score) if score != "N/A" else None)

    print("\n  Per-metric results:")
    for metric, scores in sorted(metrics_seen.items()):
        valid = [s for s in scores if s is not None]
        avg = sum(valid) / len(valid) if valid else 0
        print(f"    {metric}: {len(valid)} scores, avg={avg:.2f}, range=[{min(valid):.2f}, {max(valid):.2f}]")

    oldest = entries[-1].get("timestamp", "")
    newest = entries[0].get("timestamp", "")
    print(f"\n  Time range: {oldest} to {newest}")

    print("  PASS: Evaluation results are being produced")
    return True


def check_monitoring_metrics(headers):
    print("\n" + "=" * 60)
    print("CHECK 4: Evaluation Metrics in Cloud Monitoring")
    print("=" * 60)

    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=2)).isoformat() + "Z"
    end = now.isoformat() + "Z"

    metric_filter = (
        f'metric.type = starts_with("aiplatform.googleapis.com/online_evaluation") '
        f'AND resource.labels.reasoning_engine_id = "{AGENT_ENGINE_ID}"'
    )

    params = {
        "filter": metric_filter,
        "interval.startTime": start,
        "interval.endTime": end,
    }

    resp = requests.get(MONITORING_API, headers=headers, params=params)
    if resp.status_code != 200:
        alt_filter = (
            f'metric.type = starts_with("custom.googleapis.com/online_evaluation") '
            f'OR metric.type = starts_with("aiplatform.googleapis.com/evaluation")'
        )
        params["filter"] = alt_filter
        resp = requests.get(MONITORING_API, headers=headers, params=params)

    data = resp.json()
    time_series = data.get("timeSeries", [])

    if not time_series:
        print("  INFO: No Cloud Monitoring metrics found yet.")
        print("  This may take additional evaluator cycles to populate.")
        print("  The Console Evaluation tab reads from Cloud Monitoring.")
        print("  Results ARE in Cloud Logging (check 3), but may not have")
        print("  been exported to Monitoring metrics yet.")
        return None

    print(f"  Found {len(time_series)} metric time series")
    for ts in time_series[:5]:
        metric_type = ts.get("metric", {}).get("type", "")
        points = ts.get("points", [])
        print(f"    {metric_type}: {len(points)} data points")

    print("  PASS: Monitoring metrics are available")
    return True


def main():
    print(f"Online Monitor Verification for Agent {AGENT_ENGINE_ID}")
    print(f"Project: {PROJECT} | Region: {LOCATION}")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print()

    headers = get_auth_headers()

    results = {}
    results["evaluator"] = check_evaluator_status(headers)
    results["traces"] = check_traces(headers)
    results["logging"] = check_eval_results_in_logging(headers)
    results["monitoring"] = check_monitoring_metrics(headers)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for check, passed in results.items():
        status = "PASS" if passed else ("INFO" if passed is None else "FAIL")
        print(f"  {check:20s} {status}")

    all_critical = all(v is not False for v in results.values())
    if all_critical:
        print("\nAll critical checks passed. Online evaluation is working.")
        if results["monitoring"] is None:
            print("Cloud Monitoring metrics may need more time to appear in the Console UI.")
    else:
        print("\nSome checks failed. See details above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
