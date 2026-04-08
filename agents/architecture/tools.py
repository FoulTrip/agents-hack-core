from google.adk.tools import FunctionTool
from tools.notion.client import create_page
from tools.notion import templates
from core.logger import get_logger

logger = get_logger(__name__)

def save_architecture_to_notion(
    project_name: str,
    tech_stack: list[str],
    system_architecture: str,
    modules: list[str],
    data_model: list[str],
    api_endpoints: list[str],
    infrastructure: str
) -> dict:
    """
    Guarda el documento de arquitectura técnica en Notion.

    Args:
        project_name: Nombre del proyecto
        tech_stack: Lista de tecnologías con justificación
        system_architecture: Descripción de la arquitectura
        modules: Lista de módulos del sistema
        data_model: Lista de entidades y relaciones
        api_endpoints: Lista de endpoints principales
        infrastructure: Descripción de infraestructura

    Returns:
        Resultado estructurado de Notion (o fallback markdown).
    """
    logger.info(f"Guardando arquitectura de: {project_name}")

    try:
        blocks = [
            templates.heading1(f"Arquitectura — {project_name}"),
            templates.divider(),
            templates.heading2("Stack tecnológico"),
            *[templates.bullet(tech) for tech in tech_stack],
            templates.divider(),
            templates.heading2("Arquitectura del sistema"),
            templates.paragraph(system_architecture),
            templates.divider(),
            templates.heading2("Módulos del sistema"),
            *[templates.bullet(module) for module in modules],
            templates.divider(),
            templates.heading2("Modelo de datos"),
            *[templates.bullet(entity) for entity in data_model],
            templates.divider(),
            templates.heading2("APIs y endpoints principales"),
            *[templates.bullet(endpoint) for endpoint in api_endpoints],
            templates.divider(),
            templates.heading2("Infraestructura"),
            templates.paragraph(infrastructure),
        ]

        page = create_page(
            title=f"ARCH — {project_name}",
            content_blocks=blocks
        )

        return page
    except Exception as e:
        logger.error(f"❌ Error al guardar arquitectura en Notion: {e}")
        from tools.notion.templates import blocks_to_markdown
        return {
            "success": False,
            "url": None,
            "page_id": None,
            "markdown": blocks_to_markdown(blocks),
            "error": str(e)
        }

save_architecture_tool = FunctionTool(save_architecture_to_notion)
