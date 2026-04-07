import uuid
from core.db import db_manager
from typing import Dict, Any, Optional, Callable, List
from core.logger import get_logger
from fastapi import WebSocket

logger = get_logger(__name__)

class SessionManager:
    """Gestor de sesiones persistentes mediante Prisma"""
    
    def __init__(self):
        self.websocket_connections: Dict[str, list] = {}
        self.status_registry: Dict[str, Any] = {"active_people": {}} # userId -> metadata
        self.db = db_manager

    async def create_session(self, user_id: str, prompt: str, project_name: Optional[str] = None) -> str:
        """Crea una nueva sesión en MongoDB"""
        session_uuid = str(uuid.uuid4())
        title = project_name or prompt[:30]
        
        # Crear en DB (ObjectId para _id se genera solo, sessionId es nuestro UUID)
        new_session = await self.db.client.projectsession.create(
            data={
                "sessionId": session_uuid,
                "title": title,
                "initialPrompt": prompt,
                "status": "pending",
                "userId": user_id
            }
        )
        
        self.websocket_connections[session_uuid] = []
        logger.info(f"Sesión persistente creada: {session_uuid} para prompt: {prompt[:30]}...")
        return session_uuid

    async def update_session(self, session_id: str, **kwargs):
        """Actualiza el estado persistente de una sesión"""
        # Note: sessionId is our UUID indexing field
        await self.db.client.projectsession.update(
            where={"sessionId": session_id},
            data=kwargs #type: ignore
        )

    async def get_session(self, session_id: str) -> Optional[Any]:
        """Obtiene la sesión de MongoDB"""
        return await self.db.client.projectsession.find_unique(
            where={"sessionId": session_id},
            include={"messages": True, "notionPages": True, "githubRepos": True}
        )

    async def list_user_sessions(self, user_id: str):
        """Lista historial de chats para un usuario"""
        return await self.db.client.projectsession.find_many(
            where={"userId": user_id},
            order={"createdAt": "desc"}
        )

    async def add_message(self, session_id: str, role: str, content: str):
        """Guarda un mensaje en el historial del chat"""
        # Primero buscar el _id de la sesión
        session = await self.db.client.projectsession.find_unique(where={"sessionId": session_id})
        if session:
            await self.db.client.message.create(
                data={
                    "sessionId": session.id,
                    "role": role,
                    "content": content
                }
            )

    async def link_notion_page(self, session_id: str, title: str, url: str, page_id: str):
        session = await self.db.client.projectsession.find_unique(where={"sessionId": session_id})
        if session:
            await self.db.client.notionpage.create(
                data={
                    "sessionId": session.id,
                    "title": title,
                    "url": url,
                    "pageId": page_id
                }
            )

    async def link_github_repo(self, session_id: str, name: str, url: str, full_name: str):
        session = await self.db.client.projectsession.find_unique(where={"sessionId": session_id})
        if session:
            await self.db.client.githubrepo.create(
                data={
                    "sessionId": session.id,
                    "name": name,
                    "url": url,
                    "fullName": full_name
                }
            )

    async def add_agent_activity(self, session_id: str, agent_name: str, agent_role: str, task: str | None = None, model: str | None = None) -> str:
        """Registra el inicio de una actividad de agente"""
        session = await self.db.client.projectsession.find_unique(where={"sessionId": session_id})
        if session:
            activity = await self.db.client.agentactivity.create(
                data={
                    "sessionId": session.id,
                    "agentName": agent_name,
                    "agentRole": agent_role,
                    "taskDescription": task,
                    "status": "working",
                    "model": model
                }
            )
            return str(activity.id)
        return ""

    async def update_agent_activity(self, activity_id: str, **kwargs):
        """Actualiza métricas y estado de la actividad del agente"""
        if not activity_id: return
        await self.db.client.agentactivity.update(
            where={"id": activity_id},
            data=kwargs  # type: ignore
        )

    def add_websocket(self, session_id: str, websocket: WebSocket, user_id: str | None = None):
        if session_id not in self.websocket_connections:
            self.websocket_connections[session_id] = []
        self.websocket_connections[session_id].append(websocket)
        
        if user_id:
            from datetime import datetime
            self.status_registry["active_people"][user_id] = {
                "userId": user_id,
                "sessionId": session_id,
                "connectedAt": datetime.now().isoformat()
            }

    def remove_websocket(self, session_id: str, websocket: WebSocket, user_id: str | None = None):
        if session_id in self.websocket_connections:
            self.websocket_connections[session_id] = [
                ws for ws in self.websocket_connections[session_id] 
                if ws != websocket
            ]
        if user_id and user_id in self.status_registry["active_people"]:
            del self.status_registry["active_people"][user_id]

    async def broadcast_to_session(self, session_id: str, message: dict):
        if session_id in self.websocket_connections:
            disconnected = []
            for ws in self.websocket_connections[session_id]:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.error(f"Error enviando a WebSocket: {e}")
                    disconnected.append(ws)
            for ws in disconnected:
                self.remove_websocket(session_id, ws)

    async def send_webhook(self, url: str, payload: dict):
        if not url: return
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status < 400: logger.info(f"Webhook enviado a {url}")
                    else: logger.warning(f"Webhook falló: {response.status}")
        except Exception as e:
            logger.error(f"Error enviando webhook: {e}")