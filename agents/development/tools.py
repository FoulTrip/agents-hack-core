from google.adk.tools import FunctionTool
from tools.github.actions import create_repository, create_multiple_files, create_file
from tools.notion.client import create_page
from tools.notion import templates
from core.logger import get_logger

logger = get_logger(__name__)

def setup_project_repository(
    project_name: str,
    repo_name: str,
    description: str,
    files: dict,
) -> str:
    """
    Crea un repositorio en GitHub y sube los archivos del proyecto.

    Args:
        project_name: Nombre legible del proyecto
        repo_name: Nombre del repositorio en GitHub (sin espacios)
        description: Descripción del repositorio
        files: Diccionario con {ruta_archivo: contenido}

    Returns:
        URL del repositorio creado
    """
    logger.info(f"Configurando repositorio para: {project_name}")

    try:
        repo_info = create_repository(
            repo_name=repo_name,
            description=description,
            private=False,
        )

        results = create_multiple_files(
            repo_full_name=repo_info["full_name"],
            files=files,
            commit_message="feat: initial project structure by Software Factory",
        )

        logger.info(f"Archivos subidos: {len(results)}")

        try:
            blocks = [
                templates.heading1(f"Desarrollo — {project_name}"),
                templates.divider(),
                templates.heading2("Repositorio"),
                templates.paragraph(f"URL: {repo_info['url']}"),
                templates.divider(),
                templates.heading2("Archivos generados"),
                *[templates.bullet(r) for r in results],
            ]
            create_page(title=f"DEV — {project_name}", content_blocks=blocks)
        except Exception as notion_err:
            logger.warning(f"⚠️ No se pudo documentar en Notion: {notion_err}")

        return f"Repositorio creado: {repo_info['url']} — {len(results)} archivos subidos."
    except Exception as e:
        logger.error(f"❌ Error al configurar repositorio: {e}")
        return f"⚠️ Error al configurar el repositorio de GitHub: {str(e)}"

setup_repository_tool = FunctionTool(setup_project_repository)
create_file_tool = FunctionTool(create_file)
create_multiple_files_tool = FunctionTool(create_multiple_files)