from github import Github
from github import GithubException
from core.config import settings
from core.logger import get_logger
from core.context import get_user_context

logger = get_logger(__name__)

def get_github_client(token: str = None) -> Github:
    # Usar token proporcionado, o el del contexto del usuario, o el por defecto del sistema
    user_token = token
    if not user_token:
        ctx = get_user_context()
        if ctx: user_token = ctx.get("githubToken")
    
    return Github(user_token or settings.GITHUB_TOKEN)

def get_authenticated_user(token: str = None):
    client = get_github_client(token)
    return client.get_user()