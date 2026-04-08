from google.adk.tools import FunctionTool
from tools.github.actions import create_multiple_files
from tools.notion.client import create_page
from tools.notion import templates
from tools.local_workspace import sync_project_files_local
from core.logger import get_logger

logger = get_logger(__name__)

def save_tests_to_repository(
    project_name: str,
    repo_full_name: str,
    test_files: dict,
    coverage_summary: str,
    test_cases_summary: list[str],
) -> dict:
    """
    Sube los archivos de tests al repositorio de GitHub y documenta en Notion.

    Args:
        project_name: Nombre del proyecto
        repo_full_name: Nombre completo del repo (usuario/repo)
        test_files: Diccionario {ruta: contenido} de archivos de test
        coverage_summary: Resumen del coverage esperado
        test_cases_summary: Lista de casos de prueba principales

    Returns:
        Resultado estructurado de la subida de tests y documentación.
    """
    logger.info(f"Subiendo tests para: {project_name}")
    local_sync = sync_project_files_local(repo_full_name=repo_full_name, files=test_files)
    if local_sync.get("enabled"):
        logger.info(
            f"Tests guardados localmente: ruta={local_sync.get('local_project_path')} archivos={local_sync.get('written_count')}"
        )

    try:
        upload_result = create_multiple_files(
            repo_full_name=repo_full_name,
            files=test_files,
            commit_message="test: add test suite by QA Agent",
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
        logger.info(f"Archivos de test subidos: {len(results)}")
    except Exception as gh_err:
        logger.error(f"❌ Error al subir tests a GitHub: {gh_err}")
        return {
            "success": False,
            "repo_full_name": repo_full_name,
            "repo_url": f"https://github.com/{repo_full_name}" if repo_full_name else None,
            "created_files": list(test_files.keys()) if isinstance(test_files, dict) else [],
            "results": [],
            "notion": None,
            "local_project_path": local_sync.get("local_project_path"),
            "local_files_written": local_sync.get("written_count", 0),
            "local_errors": local_sync.get("errors", []),
            "error": str(gh_err),
            "message": f"⚠️ Error al subir tests a GitHub: {str(gh_err)}",
        }

    try:
        blocks = [
            templates.heading1(f"QA — {project_name}"),
            templates.divider(),
            templates.heading2("Repositorio"),
            templates.paragraph(f"Repo: {effective_repo_full_name}"),
            templates.divider(),
            templates.heading2("Coverage esperado"),
            templates.paragraph(coverage_summary),
            templates.divider(),
            templates.heading2("Casos de prueba"),
            *[templates.bullet(case) for case in test_cases_summary],
            templates.divider(),
            templates.heading2("Archivos generados"),
            *[templates.bullet(r) for r in results],
        ]
        notion_result = create_page(title=f"QA — {project_name}", content_blocks=blocks)
    except Exception as notion_err:
        logger.warning(f"⚠️ No se pudo documentar QA en Notion: {notion_err}")
        notion_result = None

    return {
        "success": True,
        "repo_full_name": effective_repo_full_name,
        "repo_url": effective_repo_url,
        "project_name": project_name,
        "created_files": list(test_files.keys()) if isinstance(test_files, dict) else [],
        "results": results,
        "notion": notion_result,
        "local_project_path": local_sync.get("local_project_path"),
        "local_files_written": local_sync.get("written_count", 0),
        "local_errors": local_sync.get("errors", []),
        "message": f"Tests subidos al repositorio: {len(results)} archivos.",
    }

save_tests_tool = FunctionTool(save_tests_to_repository)
