import pandas as pd
import pandas_gbq
import vertexai
from vertexai.evaluation import EvalTask, PointwiseMetric, PointwiseMetricPromptTemplate

def run_evaluation_and_export_to_bq(
    project_id: str, 
    location: str, 
    bq_dataset_id: str, 
    bq_table_id: str
):
    """
    Evaluates agent responses using a custom rubric and pushes metrics to BigQuery.
    """
    vertexai.init(project=project_id, location=location)

    # =====================================================================
    # 1. Custom Evaluation Rubric Definition
    # =====================================================================
    # We define a custom Model-as-a-Judge pointwise metric to evaluate agent quality.
    custom_helpfulness_metric = PointwiseMetric(
        metric="agent_quality_score",
        metric_prompt_template=PointwiseMetricPromptTemplate(
            criteria={
                "helpfulness": "The response must directly and accurately answer the user's initial request.",
                "conciseness": "The response must be brief. No rambling or unnecessary pleasantries."
            },
            rating_rubric={
                "1": "Fails to answer the request entirely.",
                "3": "Answers the request, but contains irrelevant rambling, or requires cognitive effort.",
                "5": "Perfect. Accurately and concisely answers the request."
            }
        )
    )

    # =====================================================================
    # 2. Gather Trial Data (Usually pulled from DB or logs)
    # =====================================================================
    eval_dataset = pd.DataFrame({
        "prompt": [
            "What is the status of billing account A100?",
            "How do I open a support ticket for GCP?"
        ],
        "response": [
            "Billing account A100 is Active.",
            "I'm just a simple mock agent and cannot open support tickets, but you can go to the Cloud Console."
        ],
        "reference": [
            "Billing account A100 is Active.",
            "Go to the Cloud Console to open a support ticket."
        ]
    })

    # =====================================================================
    # 3. Create and Run the Native EvalTask
    # =====================================================================
    print("Initiating Vertex AI EvalTask with Custom Rubric...")
    eval_task = EvalTask(
        dataset=eval_dataset,
        metrics=["exact_match", custom_helpfulness_metric],
        experiment="agent-eval-looker-experiment"
    )
    
    eval_result = eval_task.evaluate()
    
    # Retrieve the results DataFrame
    metrics_df = eval_result.metrics_table
    
    # Clean up column names for BigQuery (replace / with _)
    metrics_df.columns = [c.replace('/', '_') for c in metrics_df.columns]
    
    print("\n[Summary Metrics]")
    print(eval_result.summary_metrics)

    # =====================================================================
    # 4. BigQuery Export for Looker Dashboarding
    # =====================================================================
    # Add a timestamp to create a time-series record for Looker visualization
    metrics_df["eval_timestamp"] = pd.Timestamp.utcnow()
    metrics_df["agent_version"] = "v1.0.0" # Helpful for filtering in Looker
    
    # Optional: ensure strings are cast correctly for BigQuery
    metrics_df["prompt"] = metrics_df["prompt"].astype(str)
    metrics_df["response"] = metrics_df["response"].astype(str)

    destination_table = f"{bq_dataset_id}.{bq_table_id}"
    print(f"\nPushing telemetry data to BigQuery: {project_id}.{destination_table}")
    
    try:
        # Pushes via pandas-gbq to BigQuery (appends standard table to Looker project)
        pandas_gbq.to_gbq(
            metrics_df,
            destination_table=destination_table,
            project_id=project_id,
            if_exists="append"
        )
        print("Export completed successfully. Data is now available for Looker dashboards.")
    except Exception as e:
        print(f"Failed to push to BigQuery (check IAM & Dataset existence): {e}")

if __name__ == "__main__":
    # To test locally, replace with your actual GCP Project ID and BigQuery Dataset name
    # Ensure BigQuery Dataset exists inside your project first.
    PROJECT = "wortz-project-352116"
    LOCATION = "us-central1"
    BQ_DATASET = "agent_metrics"
    BQ_TABLE = "eval_rubric_results"
    
    print(f"Configured project parameters. Running for {PROJECT}")
    # uncomment to execute
    run_evaluation_and_export_to_bq(PROJECT, LOCATION, BQ_DATASET, BQ_TABLE)
