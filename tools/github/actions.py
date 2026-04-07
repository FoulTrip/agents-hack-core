from github import GithubException
from tools.github.client import get_github_client, get_authenticated_user
from core.logger import get_logger
import base64

logger = get_logger(__name__)

def create_repository(repo_name: str, description: str, private: bool = False) -> dict:
    client = get_github_client()
    user = get_authenticated_user()
    
    logger.info(f"Creando repositorio: {repo_name}")
    
    try:
        repo = user.create_repo(
            name=repo_name,
            description=description,
            private=private,
            auto_init=True,
        )
        logger.info(f"Repositorio creado: {repo.html_url}")
        return {"url": repo.html_url, "name": repo.name, "full_name": repo.full_name}
    except GithubException as e:
        if e.status == 422:
            logger.warning(f"Repositorio {repo_name} ya existe, usando el existente")
            repo = client.get_repo(f"{user.login}/{repo_name}")
            return {"url": repo.html_url, "name": repo.name, "full_name": repo.full_name}
        raise

def create_file(repo_full_name: str, file_path: str, content: str, commit_message: str) -> str:
    import time
    client = get_github_client()
    
    # Retry logic for 404 - sometimes GitHub takes a second to propagate new repo
    repo = None
    for attempt in range(5):
        try:
            repo = client.get_repo(repo_full_name)
            break
        except GithubException as e:
            if e.status == 404 and attempt < 4:
                logger.warning(f"Repo {repo_full_name} not found yet (attempt {attempt+1}/5). Waiting...")
                time.sleep(2)
                continue
            raise
    
    logger.debug(f"Creando archivo: {file_path} en {repo_full_name}")
    
    try:
        repo.create_file(
            path=file_path,
            message=commit_message,
            content=content,
        )
        return f"Archivo {file_path} creado exitosamente"
    except GithubException as e:
        if e.status == 422:
            contents = repo.get_contents(file_path)
            repo.update_file(
                path=file_path,
                message=f"update: {commit_message}",
                content=content,
                sha=contents.sha,
            )
            return f"Archivo {file_path} actualizado exitosamente"
        raise

def create_multiple_files(repo_full_name: str, files: dict, commit_message: str) -> list[str]:
    # Small pause to ensure GitHub is ready for writes
    import time
    time.sleep(1)
    results = []
    for file_path, content in files.items():
        result = create_file(repo_full_name, file_path, content, commit_message)
        results.append(result)
    return results