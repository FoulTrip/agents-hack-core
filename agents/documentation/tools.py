from google.adk.tools import FunctionTool
from tools.github.actions import create_multiple_files
from tools.notion.client import create_page
from tools.notion import templates
from tools.local_workspace import sync_project_files_local
from core.logger import get_logger

logger = get_logger(__name__)

def save_documentation(
    project_name: str,
    repo_full_name: str,
    doc_files: dict,
    api_endpoints_summary: list[str],
    setup_steps: list[str],
) -> dict:
    """
    Sube la documentación al repositorio de GitHub y crea página en Notion.

    Args:
        project_name: Nombre del proyecto
        repo_full_name: Nombre completo del repo (usuario/repo)
        doc_files: Diccionario {ruta: contenido} de archivos de documentación
        api_endpoints_summary: Lista de endpoints documentados
        setup_steps: Pasos de instalación resumidos

    Returns:
        Resultado estructurado con archivos subidos y respaldo de documentación.
    """
    logger.info(f"Generando documentación para: {project_name}")
    local_sync = sync_project_files_local(repo_full_name=repo_full_name, files=doc_files)
    if local_sync.get("enabled"):
        logger.info(
            f"Documentación guardada localmente: ruta={local_sync.get('local_project_path')} archivos={local_sync.get('written_count')}"
        )

    try:
        upload_result = create_multiple_files(
            repo_full_name=repo_full_name,
            files=doc_files,
            commit_message="docs: add full documentation by Documentation Agent",
            return_repo_info=True,
        )
        if isinstance(upload_result, dict):
            results = upload_result.get("results", [])
            effective_repo_full_name = upload_result.get("effective_repo_full_name", repo_full_name)
            effective_repo_url = upload_result.get("effective_repo_url", f"https://github.com/{repo_full_name}" if repo_full_name else None)
        else:
            results = upload_result
            effective_repo_full_name = repo_full_name
            effective_repo_url = f"https://github.com/{repo_full_name}" if repo_full_name else None
        logger.info(f"Archivos de documentación subidos: {len(results)}")
    except Exception as gh_err:
        logger.error(f"Error al subir documentación a GitHub: {gh_err}")
        return {
            "success": False,
            "repo_full_name": repo_full_name,
            "repo_url": f"https://github.com/{repo_full_name}" if repo_full_name else None,
            "created_files": list(doc_files.keys()) if isinstance(doc_files, dict) else [],
            "results": [],
            "notion": None,
            "local_project_path": local_sync.get("local_project_path"),
            "local_files_written": local_sync.get("written_count", 0),
            "local_errors": local_sync.get("errors", []),
            "error": str(gh_err),
            "message": f"Error al subir documentación a GitHub: {str(gh_err)}",
        }

    try:
        blocks = [
            templates.heading1(f"Documentación — {project_name}"),
            templates.divider(),
            templates.heading2("Repositorio"),
            templates.paragraph(f"Repo: {effective_repo_full_name}"),
            templates.divider(),
            templates.heading2("Endpoints documentados"),
            *[templates.bullet(ep) for ep in api_endpoints_summary],
            templates.divider(),
            templates.heading2("Pasos de instalación"),
            *[templates.bullet(step) for step in setup_steps],
            templates.divider(),
            templates.heading2("Archivos generados"),
            *[templates.bullet(r) for r in results],
        ]
        notion_result = create_page(title=f"DOCS — {project_name}", content_blocks=blocks)
    except Exception as notion_err:
        logger.warning(f"No se pudo documentar en Notion: {notion_err}")
        notion_result = None

    return {
        "success": True,
        "repo_full_name": effective_repo_full_name,
        "repo_url": effective_repo_url,
        "project_name": project_name,
        "created_files": list(doc_files.keys()) if isinstance(doc_files, dict) else [],
        "results": results,
        "notion": notion_result,
        "local_project_path": local_sync.get("local_project_path"),
        "local_files_written": local_sync.get("written_count", 0),
        "local_errors": local_sync.get("errors", []),
        "message": f"Documentación subida al repositorio: {len(results)} archivos.",
    }

save_documentation_tool = FunctionTool(save_documentation)
