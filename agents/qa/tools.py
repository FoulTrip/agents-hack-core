from google.adk.tools import FunctionTool
from tools.github.actions import create_multiple_files
from tools.notion.client import create_page
from tools.notion import templates
from core.logger import get_logger

logger = get_logger(__name__)

def save_tests_to_repository(
    project_name: str,
    repo_full_name: str,
    test_files: dict,
    coverage_summary: str,
    test_cases_summary: list[str],
) -> str:
    """
    Sube los archivos de tests al repositorio de GitHub y documenta en Notion.

    Args:
        project_name: Nombre del proyecto
        repo_full_name: Nombre completo del repo (usuario/repo)
        test_files: Diccionario {ruta: contenido} de archivos de test
        coverage_summary: Resumen del coverage esperado
        test_cases_summary: Lista de casos de prueba principales

    Returns:
        Mensaje con resultado de la operación
    """
    logger.info(f"Subiendo tests para: {project_name}")

    try:
        results = create_multiple_files(
            repo_full_name=repo_full_name,
            files=test_files,
            commit_message="test: add test suite by QA Agent",
        )
        logger.info(f"Archivos de test subidos: {len(results)}")
    except Exception as gh_err:
        logger.error(f"❌ Error al subir tests a GitHub: {gh_err}")
        return f"⚠️ Error al subir tests a GitHub: {str(gh_err)}"

    try:
        blocks = [
            templates.heading1(f"QA — {project_name}"),
            templates.divider(),
            templates.heading2("Repositorio"),
            templates.paragraph(f"Repo: {repo_full_name}"),
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
        create_page(title=f"QA — {project_name}", content_blocks=blocks)
    except Exception as notion_err:
        logger.warning(f"⚠️ No se pudo documentar QA en Notion: {notion_err}")

    return f"Tests subidos al repositorio: {len(results)} archivos."

save_tests_tool = FunctionTool(save_tests_to_repository)