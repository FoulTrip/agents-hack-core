from google.adk.tools import FunctionTool
from tools.github.actions import create_multiple_files
from tools.notion.client import create_page
from tools.notion import templates
from core.logger import get_logger

logger = get_logger(__name__)

def setup_devops_infrastructure(
    project_name: str,
    repo_full_name: str,
    devops_files: dict,
    deployment_summary: str,
    pipeline_steps: list[str],
    services: list[str],
) -> str:
    """
    Sube la configuración de infraestructura al repositorio y documenta en Notion.

    Args:
        project_name: Nombre del proyecto
        repo_full_name: Nombre completo del repo (usuario/repo)
        devops_files: Diccionario {ruta: contenido} de archivos de infraestructura
        deployment_summary: Resumen del proceso de despliegue
        pipeline_steps: Pasos del pipeline de CI/CD
        services: Lista de servicios configurados

    Returns:
        Mensaje con resultado de la operación
    """
    logger.info(f"Configurando infraestructura para: {project_name}")

    results = create_multiple_files(
        repo_full_name=repo_full_name,
        files=devops_files,
        commit_message="ci: add devops infrastructure by DevOps Agent",
    )

    logger.info(f"Archivos de infraestructura subidos: {len(results)}")

    blocks = [
        templates.heading1(f"DevOps — {project_name}"),
        templates.divider(),
        templates.heading2("Repositorio"),
        templates.paragraph(f"Repo: {repo_full_name}"),
        templates.divider(),
        templates.heading2("Resumen de despliegue"),
        templates.paragraph(deployment_summary),
        templates.divider(),
        templates.heading2("Servicios configurados"),
        *[templates.bullet(service) for service in services],
        templates.divider(),
        templates.heading2("Pipeline CI/CD"),
        *[templates.bullet(step) for step in pipeline_steps],
        templates.divider(),
        templates.heading2("Archivos generados"),
        *[templates.bullet(r) for r in results],
    ]

    create_page(
        title=f"DEVOPS — {project_name}",
        content_blocks=blocks
    )

    return f"Infraestructura configurada: {len(results)} archivos subidos. Documentado en Notion."

setup_devops_tool = FunctionTool(setup_devops_infrastructure)