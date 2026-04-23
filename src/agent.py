import vertexai


def get_billing_status(account_id: str) -> str:
    """Gets the current status of a billing account."""
    revenue_lookup = {"A100": "Active", "B200": "Suspended"}
    return revenue_lookup.get(account_id, "Unknown Account")


class FinanceAgent:
    """Agent deployed on Vertex AI Agent Engine."""

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
