"""CRUD operations and testing for Online Monitors (Online Evaluators).

Supports: list, get, create, update (pause/resume/disable), delete, and test.

Usage:
    python src/manage_online_monitors.py list
    python src/manage_online_monitors.py get <evaluator_id>
    python src/manage_online_monitors.py create
    python src/manage_online_monitors.py pause <evaluator_id>
    python src/manage_online_monitors.py resume <evaluator_id>
    python src/manage_online_monitors.py delete <evaluator_id>
    python src/manage_online_monitors.py test
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
AGENT_RESOURCE = f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{AGENT_ENGINE_ID}"

API_BASE = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_NUMBER}/locations/{LOCATION}"

DEFAULT_CONFIG = {
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
}


def get_headers():
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return {"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"}


def list_monitors():
    resp = requests.get(f"{API_BASE}/onlineEvaluators", headers=get_headers())
    resp.raise_for_status()
    monitors = resp.json().get("onlineEvaluators", [])
    print(f"Found {len(monitors)} online monitor(s)\n")
    for m in monitors:
        mid = m["name"].split("/")[-1]
        metrics = [ms["metric"]["predefinedMetricSpec"]["metricSpecName"]
                   for ms in m.get("metricSources", [])]
        print(f"  ID:      {mid}")
        print(f"  Name:    {m.get('displayName', '')}")
        print(f"  State:   {m.get('state', 'UNKNOWN')}")
        print(f"  Agent:   {m.get('agentResource', '').split('/')[-1]}")
        print(f"  Metrics: {metrics}")
        print(f"  Created: {m.get('createTime', '')}")
        if m.get("stateDetails"):
            for d in m["stateDetails"]:
                print(f"  Detail:  {d.get('message', '')}")
        print()
    return monitors


def get_monitor(evaluator_id):
    resp = requests.get(f"{API_BASE}/onlineEvaluators/{evaluator_id}", headers=get_headers())
    resp.raise_for_status()
    m = resp.json()
    print(json.dumps(m, indent=2))
    return m


def create_monitor(config=None):
    config = config or DEFAULT_CONFIG
    metrics = [ms["metric"]["predefinedMetricSpec"]["metricSpecName"]
               for ms in config["metricSources"]]
    print(f"Creating monitor '{config['displayName']}' with metrics: {metrics}")
    resp = requests.post(f"{API_BASE}/onlineEvaluators", headers=get_headers(), json=config)
    if resp.status_code == 200:
        result = resp.json()
        print(f"  Operation: {result.get('name', '')}")
        return result
    else:
        print(f"  Error {resp.status_code}: {resp.text}")
        return None


def update_monitor(evaluator_id, updates, update_mask):
    url = f"{API_BASE}/onlineEvaluators/{evaluator_id}"
    params = {"updateMask": update_mask}
    resp = requests.patch(url, headers=get_headers(), json=updates, params=params)
    if resp.status_code == 200:
        print(f"  Updated {evaluator_id}: {update_mask}")
        return resp.json()
    else:
        print(f"  Error {resp.status_code}: {resp.text}")
        return None


def pause_monitor(evaluator_id):
    print(f"Pausing monitor {evaluator_id}...")
    return update_monitor(evaluator_id, {"state": "PAUSED"}, "state")


def resume_monitor(evaluator_id):
    print(f"Resuming monitor {evaluator_id}...")
    return update_monitor(evaluator_id, {"state": "ACTIVE"}, "state")


def delete_monitor(evaluator_id):
    print(f"Deleting monitor {evaluator_id}...")
    resp = requests.delete(f"{API_BASE}/onlineEvaluators/{evaluator_id}", headers=get_headers())
    if resp.status_code == 200:
        print(f"  Deleted successfully")
        return True
    else:
        print(f"  Error {resp.status_code}: {resp.text}")
        return False


def check_eval_results(evaluator_id=None):
    headers = get_headers()
    filter_parts = [
        f'resource.type="aiplatform.googleapis.com/ReasoningEngine"',
        f'resource.labels.reasoning_engine_id="{AGENT_ENGINE_ID}"',
        f'labels."event.name"="gen_ai.evaluation.result"',
    ]
    if evaluator_id:
        filter_parts.append(
            f'labels.online_evaluator="projects/{PROJECT_NUMBER}/locations/{LOCATION}/onlineEvaluators/{evaluator_id}"'
        )

    body = {
        "resourceNames": [f"projects/{PROJECT}"],
        "filter": " ".join(filter_parts),
        "orderBy": "timestamp desc",
        "pageSize": 50,
    }
    resp = requests.post("https://logging.googleapis.com/v2/entries:list", headers=headers, json=body)
    resp.raise_for_status()
    entries = resp.json().get("entries", [])
    return entries


def run_test():
    print("=" * 60)
    print("ONLINE MONITOR INTEGRATION TEST")
    print("=" * 60)
    results = {}

    # Test 1: List monitors
    print("\n[1/5] List monitors")
    monitors = list_monitors()
    results["list"] = len(monitors) > 0
    print(f"  {'PASS' if results['list'] else 'FAIL'}: {len(monitors)} monitor(s) found")

    if not monitors:
        print("\nNo monitors exist. Run 'create' first.")
        return results

    active = [m for m in monitors if m.get("state") == "ACTIVE"]
    monitor_id = monitors[0]["name"].split("/")[-1]

    # Test 2: Get monitor detail
    print(f"\n[2/5] Get monitor {monitor_id}")
    try:
        detail = get_monitor(monitor_id)
        results["get"] = detail.get("name") is not None
        print(f"  PASS: Got monitor detail")
    except Exception as e:
        results["get"] = False
        print(f"  FAIL: {e}")

    # Test 3: Check for evaluation results in Cloud Logging
    print(f"\n[3/5] Check evaluation results in Cloud Logging")
    entries = check_eval_results()
    results["eval_results"] = len(entries) > 0
    if entries:
        metrics_seen = {}
        for e in entries:
            labels = e.get("labels", {})
            metric = labels.get("gen_ai.evaluation.name", "unknown")
            score = labels.get("gen_ai.evaluation.score.value", "N/A")
            if metric not in metrics_seen:
                metrics_seen[metric] = []
            try:
                metrics_seen[metric].append(float(score))
            except (ValueError, TypeError):
                pass

        print(f"  Found {len(entries)} evaluation entries")
        for metric, scores in sorted(metrics_seen.items()):
            avg = sum(scores) / len(scores) if scores else 0
            print(f"    {metric}: n={len(scores)}, avg={avg:.2f}")
        print(f"  PASS")
    else:
        print(f"  FAIL: No evaluation results found")

    # Test 4: Check monitor state matches expectation
    print(f"\n[4/5] Verify monitor state")
    state = monitors[0].get("state", "UNKNOWN")
    results["state"] = state in ("ACTIVE", "PAUSED")
    print(f"  State: {state}")
    print(f"  {'PASS' if results['state'] else 'FAIL'}: State is valid")

    # Test 5: Verify agent resource binding
    print(f"\n[5/5] Verify agent resource binding")
    agent_ref = monitors[0].get("agentResource", "")
    results["binding"] = AGENT_ENGINE_ID in agent_ref
    print(f"  Agent resource: {agent_ref}")
    print(f"  {'PASS' if results['binding'] else 'FAIL'}: Bound to agent {AGENT_ENGINE_ID}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = all(results.values())
    for check, passed in results.items():
        print(f"  {check:20s} {'PASS' if passed else 'FAIL'}")
    print(f"\n{'All tests passed.' if all_pass else 'Some tests failed.'}")
    return results


COMMANDS = {
    "list": lambda args: list_monitors(),
    "get": lambda args: get_monitor(args[0]) if args else print("Usage: get <evaluator_id>"),
    "create": lambda args: create_monitor(),
    "pause": lambda args: pause_monitor(args[0]) if args else print("Usage: pause <evaluator_id>"),
    "resume": lambda args: resume_monitor(args[0]) if args else print("Usage: resume <evaluator_id>"),
    "delete": lambda args: delete_monitor(args[0]) if args else print("Usage: delete <evaluator_id>"),
    "test": lambda args: run_test(),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: {sys.argv[0]} <command> [args]")
        print(f"Commands: {', '.join(COMMANDS)}")
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
