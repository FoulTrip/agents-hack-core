from notion_client import Client
from core.config import settings
from core.logger import get_logger
from core.context import get_user_context

logger = get_logger(__name__)

def get_notion_client(token: str = None) -> Client:
    # Usar token proporcionado, o el del contexto del usuario, o el por defecto del sistema
    user_token = token
    if not user_token:
        ctx = get_user_context()
        if ctx: user_token = ctx.get("notionToken")
    
    return Client(auth=user_token or settings.NOTION_TOKEN)

def create_page(title: str, content_blocks: list, token: str = None, page_id: str = None) -> dict:
    # Obtener tokens y workspace IDs del contexto si no se proporcionan
    ctx = get_user_context()
    user_token = token or (ctx.get("notionToken") if ctx else None)
    user_ws_id = page_id or (ctx.get("notionWorkspaceId") if ctx else None)
    
    client = get_notion_client(user_token)
    logger.debug(f"Creando página en Notion: {title}")
    
    # Usar el page_id del usuario o el del sistema por defecto
    parent_id = user_ws_id or settings.NOTION_WORKSPACE_ID
    
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
    return page