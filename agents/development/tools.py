from google.adk.tools import FunctionTool
from tools.github.actions import create_repository, create_multiple_files, create_file
from tools.notion.client import create_page
from tools.notion import templates
from tools.local_workspace import sync_project_files_local
from core.logger import get_logger

logger = get_logger(__name__)

def setup_project_repository(
    project_name: str,
    repo_name: str,
    description: str,
    files: dict,
) -> dict:
    """
    Crea un repositorio en GitHub y sube los archivos del proyecto.

    Args:
        project_name: Nombre legible del proyecto
        repo_name: Nombre del repositorio en GitHub (sin espacios)
        description: Descripción del repositorio
        files: Diccionario con {ruta_archivo: contenido}

    Returns:
        Resultado estructurado con información del repositorio y artefactos.
    """
    logger.info(f"Configurando repositorio para: {project_name}")
    local_sync = {
        "enabled": False,
        "local_project_path": None,
        "written_count": 0,
        "errors": [],
    }

    try:
        repo_info = create_repository(
            repo_name=repo_name,
            description=description,
            private=False,
        )
        # Sincronizar solo una vez con owner/repo para evitar carpetas duplicadas.
        local_sync = sync_project_files_local(repo_full_name=repo_info["full_name"], files=files)
        if local_sync.get("enabled"):
            logger.info(
                f"Workspace local generado para {project_name}: ruta={local_sync.get('local_project_path')} archivos={local_sync.get('written_count')}"
            )

        upload_result = create_multiple_files(
            repo_full_name=repo_info["full_name"],
            files=files,
            commit_message="feat: initial project structure by Software Factory",
            return_repo_info=True,
        )
        if isinstance(upload_result, dict):
            results = upload_result.get("results", [])
            effective_repo_full_name = upload_result.get("effective_repo_full_name", repo_info["full_name"])
            effective_repo_url = upload_result.get("effective_repo_url", repo_info["url"])
        else:
            results = upload_result
            effective_repo_full_name = repo_info["full_name"]
            effective_repo_url = repo_info["url"]

        logger.info(f"Archivos subidos: {len(results)}")

        try:
            blocks = [
                templates.heading1(f"Desarrollo — {project_name}"),
                templates.divider(),
                templates.heading2("Repositorio"),
                templates.paragraph(f"URL: {effective_repo_url}"),
                templates.divider(),
                templates.heading2("Archivos generados"),
                *[templates.bullet(r) for r in results],
            ]
            notion_result = create_page(title=f"DEV — {project_name}", content_blocks=blocks)
        except Exception as notion_err:
            logger.warning(f"No se pudo documentar en Notion: {notion_err}")
            notion_result = None

        return {
            "success": True,
            "repo_url": effective_repo_url,
            "repo_full_name": effective_repo_full_name,
            "project_name": project_name,
            "created_files": list(files.keys()),
            "results": results,
            "notion": notion_result,
            "local_project_path": local_sync.get("local_project_path"),
            "local_files_written": local_sync.get("written_count", 0),
            "local_errors": local_sync.get("errors", []),
            "message": f"Repositorio creado: {effective_repo_url} — {len(results)} archivos subidos.",
        }
    except Exception as e:
        logger.error(f"Error al configurar repositorio: {e}")
        # Fallback: mantener generación local incluso si falla GitHub.
        if not local_sync.get("local_project_path"):
            local_sync = sync_project_files_local(repo_full_name=repo_name, files=files)
        return {
            "success": False,
            "repo_url": None,
            "repo_full_name": None,
            "project_name": project_name,
            "created_files": list(files.keys()) if isinstance(files, dict) else [],
            "results": [],
            "notion": None,
            "local_project_path": local_sync.get("local_project_path"),
            "local_files_written": local_sync.get("written_count", 0),
            "local_errors": local_sync.get("errors", []),
            "error": str(e),
            "message": f"Error al configurar el repositorio de GitHub: {str(e)}",
        }

setup_repository_tool = FunctionTool(setup_project_repository)
create_file_tool = FunctionTool(create_file)
create_multiple_files_tool = FunctionTool(create_multiple_files)
