import vertexai

# ==============================================================================
# Agent Engine Deployment Mock Structure
# ==============================================================================

def get_billing_status(account_id: str) -> str:
    """Gets the current status of a billing account."""
    revenue_lookup = {"A100": "Active", "B200": "Suspended"}
    return revenue_lookup.get(account_id, "Unknown Account")


class FinanceAgent:
    """A template Agent to be deployed on Vertex AI Agent Engine."""
    
    def __init__(self, project: str, location: str):
        vertexai.init(project=project, location=location)

    def set_up(self):
        """Initializes model configs on first deployment."""
        from vertexai.generative_models import GenerativeModel
        self.model_name = "gemini-1.5-pro-preview-0409"
        self.model = GenerativeModel(self.model_name)
        self.system_prompt = "You are a helpful finance agent focused on Google Cloud billing."

    def query(self, prompt: str) -> str:
        """The entrypoint invoked by Agent Engine."""
        response = self.model.generate_content(
            [self.system_prompt, prompt]
        )
        return response.text


# How a user deploys this agent into Vertex AI Agent Engine:
# 
# engine = reasoning_engines.ReasoningEngine.create(
#     FinanceAgent(project="your-project-id", location="us-central1"),
#     requirements=["google-cloud-aiplatform", "google-cloud-bigquery"],
#     display_name="Demo Finance Agent Engine"
# )
