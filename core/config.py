from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    GEMINI_API_KEY: str      = os.getenv("GEMINI_API_KEY", "")
    GITHUB_TOKEN: str        = os.getenv("GITHUB_TOKEN", "")
    NOTION_TOKEN: str        = os.getenv("NOTION_TOKEN", "")
    NOTION_WS_ID: str        = os.getenv("NOTION_WORKSPACE_ID", "")
    NOTION_WORKSPACE_ID: str = os.getenv("NOTION_WORKSPACE_ID", "")  # alias for client compatibility
    LOG_LEVEL: str           = os.getenv("LOG_LEVEL", "INFO")
    ENVIRONMENT: str         = os.getenv("ENVIRONMENT", "development")
    JWT_SECRET: str          = os.getenv("JWT_SECRET", "change_me_to_something_very_long_at_least_32_characters")
    JWT_ALGORITHM: str       = os.getenv("JWT_ALGORITHM", "HS256")
    
    # Vertex AI configuration
    GOOGLE_CLOUD_PROJECT: str  = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    GOOGLE_GENAI_USE_VERTEXAI: str = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")

    def validate(self):
        required = {
            "GEMINI_API_KEY": self.GEMINI_API_KEY,
            "GITHUB_TOKEN": self.GITHUB_TOKEN,
            "NOTION_TOKEN": self.NOTION_TOKEN,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise EnvironmentError(f"Faltan variables de entorno: {missing}")

settings = Settings()