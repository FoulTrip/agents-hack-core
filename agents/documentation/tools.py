from google.adk.tools import FunctionTool
from tools.github.actions import create_multiple_files
from tools.notion.client import create_page
from tools.notion import templates
from core.logger import get_logger

logger = get_logger(__name__)

def save_documentation(
    project_name: str,
    repo_full_name: str,
    doc_files: dict,
    api_endpoints_summary: list[str],
    setup_steps: list[str],
) -> str:
    """
    Sube la documentación al repositorio de GitHub y crea página en Notion.

    Args:
        project_name: Nombre del proyecto
        repo_full_name: Nombre completo del repo (usuario/repo)
        doc_files: Diccionario {ruta: contenido} de archivos de documentación
        api_endpoints_summary: Lista de endpoints documentados
        setup_steps: Pasos de instalación resumidos

    Returns:
        Mensaje con resultado de la operación
    """
    logger.info(f"Generando documentación para: {project_name}")

    try:
        results = create_multiple_files(
            repo_full_name=repo_full_name,
            files=doc_files,
            commit_message="docs: add full documentation by Documentation Agent",
        )
        logger.info(f"Archivos de documentación subidos: {len(results)}")
    except Exception as gh_err:
        logger.error(f"❌ Error al subir documentación a GitHub: {gh_err}")
        return f"⚠️ Error al subir documentación a GitHub: {str(gh_err)}"

    try:
        blocks = [
            templates.heading1(f"Documentación — {project_name}"),
            templates.divider(),
            templates.heading2("Repositorio"),
            templates.paragraph(f"Repo: {repo_full_name}"),
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
        create_page(title=f"DOCS — {project_name}", content_blocks=blocks)
    except Exception as notion_err:
        logger.warning(f"⚠️ No se pudo documentar en Notion: {notion_err}")

    return f"Documentación subida al repositorio: {len(results)} archivos."

save_documentation_tool = FunctionTool(save_documentation)