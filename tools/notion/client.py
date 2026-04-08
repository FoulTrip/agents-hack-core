from notion_client import Client
from core.config import settings
from core.logger import get_logger
from core.context import get_user_context
from pathlib import Path
import re

logger = get_logger(__name__)

def get_notion_client(token: str = None) -> Client:
    # Usar token proporcionado, o el del contexto del usuario, o el por defecto del sistema
    user_token = token
    if not user_token:
        ctx = get_user_context()
        if ctx: user_token = ctx.get("notionToken")
    
    return Client(auth=user_token or settings.NOTION_TOKEN)


def _slugify_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", value or "")
    safe = safe.strip("-._")
    return safe or "document"


def _save_markdown_local(title: str, markdown_content: str, ctx: dict | None) -> dict:
    try:
        from tools.local_workspace import sync_project_files_local

        session_id = str((ctx or {}).get("session_id") or "global")
        session_safe = _slugify_filename(session_id)
        repo_ref = f"session/{session_safe}"
        rel_path = f"docs/notion/{_slugify_filename(title)}.md"

        sync = sync_project_files_local(
            repo_full_name=repo_ref,
            files={rel_path: markdown_content}
        )

        local_markdown_path = None
        if sync.get("local_project_path"):
            local_markdown_path = str((Path(sync["local_project_path"]) / rel_path).resolve())

        return {
            "local_project_path": sync.get("local_project_path"),
            "local_markdown_path": local_markdown_path,
            "local_files_written": sync.get("written_count", 0),
            "local_errors": sync.get("errors", []),
        }
    except Exception as e:
        logger.warning(f"⚠️ No se pudo guardar markdown local para '{title}': {e}")
        return {
            "local_project_path": None,
            "local_markdown_path": None,
            "local_files_written": 0,
            "local_errors": [str(e)],
        }


def create_page(title: str, content_blocks: list, token: str = None, page_id: str = None) -> dict | None:
    # Obtener tokens y workspace IDs del contexto si no se proporcionan
    ctx = get_user_context()
    user_token = token or (ctx.get("notionToken") if ctx else None)
    user_ws_id = page_id or (ctx.get("notionWorkspaceId") if ctx else None)
    
    # 1. Preparar el contenido Markdown (siempre necesario para fallback)
    from .templates import blocks_to_markdown
    markdown_content = blocks_to_markdown(content_blocks)
    local_save = _save_markdown_local(title=title, markdown_content=markdown_content, ctx=ctx)

    if not settings.NOTION_UPLOAD_ENABLED:
        logger.info(
            f"Notion deshabilitado por configuración. Documento guardado localmente: {local_save.get('local_markdown_path')}"
        )
        return {
            "success": True,
            "url": None,
            "page_id": None,
            "markdown": markdown_content,
            "uploaded_to_notion": False,
            **local_save,
        }
    
    if not user_token:
        logger.warning("⚠️ No hay token de Notion disponible. Usando fallback local.")
        return {
            "success": True,
            "url": None,
            "page_id": None,
            "markdown": markdown_content,
            "uploaded_to_notion": False,
            **local_save,
        }

    client = get_notion_client(user_token)
    logger.debug(f"Creando página en Notion: {title}")
    
    # Usar el page_id del usuario o el del sistema por defecto
    parent_id = user_ws_id or settings.NOTION_WORKSPACE_ID
    source = "Usuario/Sesión" if user_ws_id else "Configuración (.env)"
    
    if not parent_id:
        logger.warning(f"⚠️ No hay Notion Workspace ID configurado. Usando fallback local.")
        return {
            "success": True,
            "url": None,
            "page_id": None,
            "markdown": markdown_content,
            "uploaded_to_notion": False,
            **local_save,
        }
        
    logger.debug(f"Intentando usar parent_id: {parent_id} (Origen: {source})")
    
    try:
        page = client.pages.create(
            parent={"page_id": parent_id},
            properties={
                "title": {
                    "title": [{"text": {"content": title}}]
                }
            },
            children=content_blocks
        )
        logger.info(f"Página creada: {page['url']}")
        return {
            "success": True, 
            "url": page['url'], 
            "page_id": page['id'], 
            "markdown": markdown_content,
            "uploaded_to_notion": True,
            **local_save,
        }
    except Exception as e:
        logger.error(f"❌ Error al crear página en Notion (parent_id={parent_id}): {e}")
        return {
            "success": True, 
            "url": None, 
            "page_id": None, 
            "markdown": markdown_content,
            "uploaded_to_notion": False,
            **local_save,
        }
