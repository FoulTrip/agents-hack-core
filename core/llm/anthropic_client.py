from anthropic import AnthropicVertex
import os

class ClaudeVertexClient:
    def __init__(self, region="us-central1", project_id=None):
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.region = region
        self.client = AnthropicVertex(region=self.region, project_id=self.project_id)

    async def generate_response(self, system_instruction: str, prompt: str, model="claude-3-5-sonnet@20240620"):
        response = self.client.messages.create(
            max_tokens=4096,
            system=system_instruction,
            messages=[
                {"role": "user", "content": prompt}
            ],
            model=model,
        )
        return response.content[0].text
