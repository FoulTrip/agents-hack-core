from google.adk.tools import FunctionTool
from tools.notion.client import create_page
from tools.notion import templates
from core.logger import get_logger

logger = get_logger(__name__)

def save_requirements_to_notion(
    project_name: str,
    summary: str,
    user_stories: list[str],
    functional_requirements: list[str],
    non_functional_requirements: list[str],
    main_features: list[str]
) -> str:
    """
    Guarda el documento de requerimientos en Notion.
    
    Args:
        project_name: Nombre del proyecto
        summary: Resumen del proyecto
        user_stories: Lista de historias de usuario
        functional_requirements: Lista de requerimientos funcionales
        non_functional_requirements: Lista de requerimientos no funcionales
        main_features: Lista de funcionalidades principales
    
    Returns:
        URL de la página creada en Notion
    """
    logger.info(f"Guardando requerimientos de: {project_name}")
    
    blocks = [
        templates.heading1(f"Requerimientos — {project_name}"),
        templates.divider(),
        templates.heading2("Resumen del proyecto"),
        templates.paragraph(summary),
        templates.divider(),
        templates.heading2("Historias de usuario"),
        *[templates.bullet(story) for story in user_stories],
        templates.divider(),
        templates.heading2("Requerimientos funcionales"),
        *[templates.bullet(req) for req in functional_requirements],
        templates.divider(),
        templates.heading2("Requerimientos no funcionales"),
        *[templates.bullet(req) for req in non_functional_requirements],
        templates.divider(),
        templates.heading2("Funcionalidades principales"),
        *[templates.bullet(feature) for feature in main_features],
    ]
    
    page = create_page(
        title=f"PRD — {project_name}",
        content_blocks=blocks
    )
    
    return f"Requerimientos guardados exitosamente en Notion: {page['url']}"

save_requirements_tool = FunctionTool(save_requirements_to_notion)