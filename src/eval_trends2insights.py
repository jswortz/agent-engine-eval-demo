"""Evaluate trends2insights Agent Engine (8788263399906607104) responses and export to BigQuery."""

import pandas as pd
import pandas_gbq
import vertexai
from vertexai.evaluation import EvalTask, PointwiseMetric, PointwiseMetricPromptTemplate

PROJECT = "wortz-project-352116"
LOCATION = "us-central1"
BQ_DATASET = "agent_metrics"
BQ_TABLE = "eval_rubric_results"
AGENT_VERSION = "v2.0.0-trends2insights"
AGENT_ENGINE_ID = "8788263399906607104"

vertexai.init(project=PROJECT, location=LOCATION)

prompts = [
    "What are the latest trends in cloud computing?",
    "Our brand is TechVista, we sell AI-powered analytics dashboards for enterprise CTOs. Key selling points are real-time insights and natural language queries. Find us the top search trends.",
    "Brand: CloudNova, Product: serverless GPU compute platform, Target: ML engineers at startups, Key selling points: 10x cheaper than AWS, auto-scaling. What YouTube trends should we target?",
    "Brand: GreenScale, Product: carbon-neutral cloud infrastructure, Target: sustainability-focused CTOs, Key selling points: zero-emission data centers, ESG reporting built-in. Analyze both Google Search and YouTube trends for our campaign.",
]

responses = [
    "Hello! I'm your Chief Marketing Officer, and I'm excited to help you build a high-impact campaign. Cloud computing is a fast-moving space, and to find the most relevant trends for your specific needs, I need to set up our campaign context. Before we dive into the real-time data from Google Search and YouTube, could you provide a few details? 1. Brand Name 2. Product Name 3. Target Audience 4. Key Selling Points. Once I have these, I can pull the exact trends we need to make this campaign a success!",
    "It's a pleasure to work with you on the TechVista campaign. As a CMO, I know how critical real-time insights are for CTOs managing complex enterprise environments. I've gathered the latest trending data from Google Search and YouTube to find a compelling hook for our campaign. Google Search Trends include: barcelona - celta de vigo (rank 1), tsla stock (rank 10), is today earth day (rank 8). YouTube Trends include: CLAYFACE teaser, Assassin's Creed showcase, Lawrence O'Donnell. Which Google Search trend number and YouTube trend number would you like to target for the TechVista campaign? Search #10 (TSLA stock) and YouTube #7 could offer interesting angles on data and analysis.",
    "It is a pleasure to meet you. As the Chief Marketing Officer for this initiative, I am excited to help CloudNova disrupt the GPU compute market. ML engineers at startups are a discerning audience, and positioning our serverless platform as a cost-effective, auto-scaling alternative is brilliant. I've gathered real-time data from Google Search and YouTube trends. Google Search: tsla stock, earth day, barcelona. YouTube: Ozuna, Clayface, Assassin's Creed Black Flag. For ML engineers, something tech-adjacent like 'tsla stock' or a high-energy 'Assassin's Creed' could provide a compelling visual or thematic hook. Which trends would you like to target?",
    "It's a pleasure to be working on the GreenScale campaign. Transitioning to carbon-neutral cloud infrastructure is critical for any modern enterprise. I've gathered the latest live trends. Strategic Note: Search trend #8 ('is today earth day') is remarkably aligned with GreenScale's sustainability mission. For YouTube, the high-tech intrigue of 'Clayface' or the 'Assassin's Creed' showcase could provide a compelling hook for a technical audience. Google Search Trends and YouTube Trends tables provided with 15 options each. Which Google Search trend and YouTube trend would you like to target?",
]

references = [
    "The agent should acknowledge the request and ask for campaign context (brand, product, audience, selling points) before providing trend data.",
    "The agent should set up the campaign for TechVista, gather real-time Google Search and YouTube trends, present them in a clear format, and suggest relevant trend pairings for enterprise analytics dashboards.",
    "The agent should set up the campaign for CloudNova, gather trends, and suggest YouTube trends relevant to ML engineers and GPU compute, such as tech-related content.",
    "The agent should set up the campaign for GreenScale, gather trends, identify Earth Day as a sustainability-aligned search trend, and present both Google Search and YouTube trend options.",
]

custom_metric = PointwiseMetric(
    metric="agent_quality_score",
    metric_prompt_template=PointwiseMetricPromptTemplate(
        criteria={
            "helpfulness": "The response must directly and accurately answer the user's request, providing actionable marketing insights.",
            "conciseness": "The response must be well-organized and not excessively verbose.",
            "tool_usage": "The agent should correctly use tools (setup_campaign, gather_trends) to gather real-time data rather than hallucinating.",
            "strategic_insight": "The agent should provide strategic recommendations that align the brand with relevant trends.",
        },
        rating_rubric={
            "1": "Completely fails to address the request or provides irrelevant information",
            "2": "Partially addresses the request but misses key elements",
            "3": "Adequately addresses the request with basic trend information",
            "4": "Good response with relevant trends and some strategic insight",
            "5": "Excellent response with real-time trends, strategic recommendations, and clear brand alignment",
        },
    ),
)

dataset = pd.DataFrame({
    "prompt": prompts,
    "response": responses,
    "reference": references,
})

print(f"Running evaluation on {len(dataset)} prompts...")
print(f"Agent Engine: {AGENT_ENGINE_ID}")
print(f"Agent Version: {AGENT_VERSION}\n")

task = EvalTask(
    dataset=dataset,
    metrics=["exact_match", custom_metric],
    experiment="trends2insights-eval",
)

result = task.evaluate()
metrics_df = result.metrics_table
metrics_df.columns = [c.replace("/", "_") for c in metrics_df.columns]
metrics_df["eval_timestamp"] = pd.Timestamp.utcnow()
metrics_df["agent_version"] = AGENT_VERSION
print("\n[Columns]")
print(list(metrics_df.columns))

print("\n[Summary Metrics]")
for k, v in result.summary_metrics.items():
    print(f"  {k}: {v}")

print("\n[Per-Row Scores]")
for i, row in metrics_df.iterrows():
    print(f"  Row {i}:")
    for c in metrics_df.columns:
        if "score" in c or "match" in c or "explanation" in c:
            print(f"    {c}: {row[c]}")

destination_table = f"{BQ_DATASET}.{BQ_TABLE}"
print(f"\nExporting to BigQuery: {PROJECT}.{destination_table}")
pandas_gbq.to_gbq(
    metrics_df,
    destination_table=destination_table,
    project_id=PROJECT,
    if_exists="append",
)
print("Export completed successfully.")
