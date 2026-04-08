from github import GithubException
from tools.github.client import get_github_client, get_authenticated_user
from core.logger import get_logger
from core.context import get_user_context
from tools.file_map import flatten_files_payload
import base64

logger = get_logger(__name__)


def _normalize_repo_full_name(repo_full_name: str) -> str:
    raw = (repo_full_name or "").strip()
    raw = raw.replace("https://github.com/", "").replace("http://github.com/", "")
    raw = raw.strip().strip("/")
    if raw.lower().endswith(".git"):
        raw = raw[:-4]
    return raw


def _resolve_effective_repo_full_name(repo_full_name: str) -> str:
    requested = _normalize_repo_full_name(repo_full_name)
    ctx = get_user_context() or {}
    forced = _normalize_repo_full_name(ctx.get("lockedRepoFullName") or "")
    if forced:
        if requested and requested != forced:
            logger.warning(
                f"Repo solicitado {requested} sobrescrito por repo oficial bloqueado de sesión: {forced}"
            )
        return forced
    return requested


def _safe_repo_path(file_path: str) -> str | None:
    raw = (file_path or "").replace("\\", "/").strip().strip("\"'").lstrip("/")
    if not raw:
        return None
    parts: list[str] = []
    for piece in raw.split("/"):
        part = (piece or "").strip().strip("\"'")
        if not part or part == ".":
            continue
        if part == "..":
            return None
        parts.append(part)
    if not parts:
        return None
    return "/".join(parts)


def create_repository(repo_name: str, description: str, private: bool = False) -> dict:
    client = get_github_client()
    user = get_authenticated_user()
    repo_name = (repo_name or "").strip()
    if repo_name.lower().endswith(".git"):
        repo_name = repo_name[:-4]
    
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
    repo_full_name = _resolve_effective_repo_full_name(repo_full_name)
    
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
    
    safe_path = _safe_repo_path(file_path)
    if not safe_path:
        raise ValueError(f"Ruta de archivo inválida para GitHub: {file_path}")

    logger.debug(f"Creando archivo: {safe_path} en {repo_full_name}")
    
    try:
        repo.create_file(
            path=safe_path,
            message=commit_message,
            content=content,
        )
        return f"Archivo {safe_path} creado exitosamente"
    except GithubException as e:
        if e.status == 422:
            contents = repo.get_contents(safe_path)
            repo.update_file(
                path=safe_path,
                message=f"update: {commit_message}",
                content=content,
                sha=contents.sha,
            )
            return f"Archivo {safe_path} actualizado exitosamente"
        raise

def create_multiple_files(
    repo_full_name: str,
    files: dict,
    commit_message: str,
    return_repo_info: bool = False,
) -> list[str] | dict:
    # Small pause to ensure GitHub is ready for writes
    import time
    time.sleep(1)
    
    client = get_github_client()
    user = get_authenticated_user()
    
    effective_repo_full_name = _resolve_effective_repo_full_name(repo_full_name)
    normalized_files = flatten_files_payload(files)
    if not normalized_files:
        logger.warning(f"No hay archivos válidos para subir a GitHub en repo {effective_repo_full_name}")
        if return_repo_info:
            return {
                "results": [],
                "effective_repo_full_name": effective_repo_full_name,
                "effective_repo_url": f"https://github.com/{effective_repo_full_name}",
            }
        return []

    # Check if repo exists, if not, try to create it
    try:
        repo = client.get_repo(effective_repo_full_name)
    except GithubException as e:
        if e.status == 404:
            # Try to create the repo
            repo_name = effective_repo_full_name.split('/')[-1]
            user_name = effective_repo_full_name.split('/')[0]
            if user_name == user.login:
                logger.info(f"Repo {effective_repo_full_name} not found, creating it...")
                try:
                    repo = user.create_repo(name=repo_name, description="Auto-generated by Software Factory", private=False, auto_init=True)
                except GithubException as create_e:
                    logger.error(f"Failed to create repo {effective_repo_full_name}: {create_e}")
                    raise e
            else:
                # Fallback defensivo: usar el owner autenticado cuando llega un owner inválido/no accesible.
                fallback_repo_full_name = f"{user.login}/{repo_name}"
                logger.warning(
                    f"Repo {effective_repo_full_name} not found under external owner. Falling back to authenticated owner: {fallback_repo_full_name}"
                )
                try:
                    repo = client.get_repo(fallback_repo_full_name)
                    effective_repo_full_name = fallback_repo_full_name
                except GithubException as fallback_get_err:
                    if fallback_get_err.status == 404:
                        try:
                            repo = user.create_repo(
                                name=repo_name,
                                description="Auto-generated by Software Factory",
                                private=False,
                                auto_init=True
                            )
                            effective_repo_full_name = fallback_repo_full_name
                        except GithubException:
                            raise e
                    else:
                        raise e
        else:
            raise
    
    results = []
    for file_path, content in normalized_files.items():
        safe_path = _safe_repo_path(file_path)
        if not safe_path:
            logger.warning(f"Ruta inválida omitida al subir a GitHub: {file_path}")
            continue
        result = create_file(effective_repo_full_name, safe_path, content, commit_message)
        results.append(result)
    if return_repo_info:
        return {
            "results": results,
            "effective_repo_full_name": effective_repo_full_name,
            "effective_repo_url": f"https://github.com/{effective_repo_full_name}",
        }
    return results
