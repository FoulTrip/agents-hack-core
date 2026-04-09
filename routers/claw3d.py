from typing import Optional
from fastapi import APIRouter, Request
from core.db import db_manager
from core.logger import get_logger
from models import DEFAULT_AGENTS
from datetime import datetime
import json
import uuid

logger = get_logger(__name__)
router = APIRouter(tags=["claw3d"])


@router.get("/health")
async def claw3d_health():
    """Health check for Claw3D discovery"""
    return {"ok": True, "status": "running", "vendor": "TripKode"}


@router.get("/api/office/presence")
async def claw3d_presence(sessionId: Optional[str] = None):
    """Informa de la presencia de agentes para todas las salas de sesiones."""
    agents_presence = []
    
    sessions = []
    if sessionId:
        s = await db_manager.client.projectsession.find_unique(where={"sessionId": sessionId})
        if s: sessions = [s]
    else:
        sessions = await db_manager.client.projectsession.find_many(order={"createdAt": "desc"}, take=5)

    working_activities = await db_manager.client.agentactivity.find_many(
        where={"status": "working"},
        order={"startTime": "desc"}
    )
    working_map = {f"{a.sessionId}_{a.agentRole}": a for a in working_activities}

    for i, agent_def in enumerate(DEFAULT_AGENTS):
        role = agent_def["role"]
        is_working = f"main_{role}" in working_map
        
        agents_presence.append({
            "agentId": f"main_{role}",
            "name": agent_def["name"],
            "status": "working" if is_working else "idle",
            "preferredDeskId": f"main:desk_{i}"
        })

    for sess in sessions:
        s_id = sess.sessionId
        for i, agent_def in enumerate(DEFAULT_AGENTS):
            role = agent_def["role"]
            is_working = f"{s_id}_{role}" in working_map
            project_label = getattr(sess, "projectName", None) or getattr(sess, "project_name", None) or "..."
            
            agents_presence.append({
                "agentId": f"{s_id}_{role}",
                "name": f"{agent_def['name']} ({project_label[:10]})",
                "status": "working" if is_working else "idle",
                "preferredDeskId": f"{s_id}:desk_{i}"
            })

    # 3. Incluir Usuarios Humanos (Presencia Multi-usuario)
    from services.pipeline import session_manager
    human_presence = []
    active_people = session_manager.status_registry.get("active_people", {})
    
    for uid, upath in active_people.items():
        human_presence.append({
            "id": uid,
            "type": "human",
            "name": f"Admin (ID: {uid[:5]})",
            "sessionId": upath.get("sessionId")
        })

    return {
        "workspaceId": sessionId or "tripkode-mega-factory",
        "timestamp": datetime.now().isoformat(),
        "agents": agents_presence,
        "humans": human_presence,
        "runtime": {
            "name": "TripKode Dynamic Factory",
            "active_rooms": len(sessions) + 1,
            "connected_admins": len(human_presence)
        }
    }


@router.get("/api/office/layout")
async def claw3d_layout(sessionId: Optional[str] = None, userId: Optional[str] = None, token: Optional[str] = None):
    """Retorna la fábrica completa del usuario en un solo documento JSON."""
    user_id = userId
    if not user_id:
        first_user = await db_manager.client.user.find_first()
        if first_user:
            user_id = str(first_user.id)
            
    if not user_id:
        return {
            "snapshot": {
                "furniture": [], "width": 1800, "height": 900, "timestamp": datetime.now().isoformat(), "gatewayUrl": "http://localhost:8000"
            }
        }

    overall_layout = await db_manager.client.workspacelayout.find_unique(where={"wingId": user_id})
    
    if not overall_layout:
        hq_furn = []
        offset_x = 0
        wing_id = "main"
        
        hq_furn.append({"_uid": f"wall_n_{wing_id}", "type": "wall", "x": offset_x, "y": 0, "w": 1800, "h": 10})
        hq_furn.append({"_uid": f"wall_s_{wing_id}", "type": "wall", "x": offset_x, "y": 890, "w": 1800, "h": 10})
        hq_furn.append({"_uid": f"wall_w_{wing_id}", "type": "wall", "x": offset_x, "y": 0, "w": 10, "h": 900})
        hq_furn.append({"_uid": f"wall_e_{wing_id}", "type": "wall", "x": offset_x + 1790, "y": 0, "w": 10, "h": 900})
        
        hq_furn.append({
            "_uid": f"label_{wing_id}", 
            "type": "floor_logo", 
            "x": offset_x + 800, "y": 400, "w": 200, "h": 100, 
            "text": "PROJECT: MAIN HQ"
        })

        hq_furn.append({"_uid": f"mr_wall_v_{wing_id}", "type": "wall", "x": offset_x + 500, "y": 0, "w": 10, "h": 400})
        hq_furn.append({"_uid": f"mr_wall_h_{wing_id}", "type": "wall", "x": offset_x, "y": 400, "w": 400, "h": 10})
        hq_furn.append({"_uid": f"meeting_table_{wing_id}", "type": "round_table", "x": offset_x + 150, "y": 150, "w": 200, "h": 200})

        for i in range(6):
            row = i // 3
            col = i % 3
            desk_x = offset_x + 700 + col * 350
            desk_y = 150 + row * 350
            global_desk_id = f"{wing_id}:desk_{i}"
            
            hq_furn.append({"_uid": global_desk_id, "type": "desk_cubicle", "x": desk_x, "y": desk_y, "facing": 180})
            hq_furn.append({"_uid": f"chair_{wing_id}_{i}", "type": "chair", "x": desk_x + 35, "y": desk_y + 60, "facing": 0})
            hq_furn.append({"_uid": f"comp_{wing_id}_{i}", "type": "computer", "x": desk_x + 35, "y": desk_y + 15, "facing": 0})

        hq_furn.extend([
            {"_uid": "couch_1", "type": "couch", "x": 100, "y": 600, "facing": 90},
            {"_uid": "couch_2", "type": "couch", "x": 100, "y": 750, "facing": 90},
            {"_uid": "coffee_machine", "type": "coffee_machine", "x": 50, "y": 800, "facing": 90},
            {"_uid": "plant_1", "type": "plant", "x": 50, "y": 450},
            {"_uid": "tv", "type": "whiteboard", "x": 480, "y": 650, "facing": 270}
        ])

        hq_furn.extend([
            {"_uid": "rack_1", "type": "server_rack", "x": 1650, "y": 100, "facing": 270},
            {"_uid": "rack_2", "type": "server_rack", "x": 1650, "y": 250, "facing": 270},
            {"_uid": "vending_1", "type": "vending", "x": 1650, "y": 700, "facing": 270}
        ])

        overall_layout = await db_manager.client.workspacelayout.create(data={
            "userId": user_id,
            "wingId": user_id,
            "wingLabel": "Company Factory",
            "offsetX": 0,
            "furniture": json.dumps(hq_furn)
        })
        
    furniture = json.loads(overall_layout.furniture)

    total_width = 1800
    for item in furniture:
        if item.get("type") == "wall" and item.get("w") == 1800:
            end_x = item.get("x", 0) + 2000
            if end_x > total_width:
                total_width = end_x

    return {
        "gatewayUrl": f"http://localhost:8000{'?sessionId='+sessionId if sessionId else ''}",
        "timestamp": datetime.now().isoformat(),
        "width": total_width,
        "height": 900,
        "country": "CO",
        "furniture": furniture
    }


@router.get("/registry")
async def claw3d_registry():
    """Registry of models available for the agents"""
    return {
        "models": {
            "gemini-pro": {"name": "Google Gemini Pro", "context": 32000, "provider": "Google"},
            "gemini-flash": {"name": "Google Gemini Flash", "context": 1000000, "provider": "Google"}
        }
    }


@router.post("/v1/chat/completions")
async def claw3d_chat(request: Request):
    """Endpoint compatible con Claw3D que usa los agentes reales de ADK."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    from agents.orchestrator.agent import create_orchestrator

    try:
        data = await request.json()
    except:
        return {"error": "Invalid JSON"}, 400
        
    messages = data.get("messages", [])
    if not messages:
        return {"error": "No messages found"}, 400
        
    user_message = messages[-1].get("content", "")
    agent_id = data.get("agentId") or data.get("model") or "orchestrator"
    
    logger.info(f"Claw3D Chat request for agent: {agent_id}")

    try:
        actual_role = agent_id or "Orchestrator"
        active_session_id = None
        
        if agent_id and "_" in agent_id:
            parts = agent_id.split("_", 1)
            active_session_id = parts[0]
            actual_role = parts[1]
            logger.info(f"Chat ruteado para sesión: {active_session_id}, Rol: {actual_role}")

        display_name = actual_role
        user_id_context = data.get("userId")
        
        final_instruction = f"Eres el rol '{display_name}' en la Software Factory."
        agent_db = None
        
        if user_id_context:
            try:
                agent_db = await db_manager.client.agent.find_first(
                    where={
                        "userId": user_id_context,
                        "OR": [
                            {"name": display_name},
                            {"role": display_name}
                        ]
                    }
                )
                if agent_db:
                    personality = getattr(agent_db, "personality", "") or ""
                    description = getattr(agent_db, "description", "") or ""
                    guidelines = getattr(agent_db, "guidelines", "") or ""
                    
                    final_instruction = f"Nombre: {agent_db.name}\nRol: {agent_db.role}\n\n"
                    final_instruction += f"Descripción: {description}\n"
                    final_instruction += f"Personalidad: {personality}\n"
                    final_instruction += f"Guías: {guidelines}\n\n"
                    final_instruction += "Responde como este agente específico en la oficina Claw3D de forma profesional."
                    logger.info(f"Usando perfil personalizado para: {agent_db.name} (Usuario: {user_id_context})")
            except Exception as db_err:
                logger.warning(f"No se pudo cargar perfil de DB: {db_err}")

        if not agent_db:
            role_instructions = {
                "Architect Agent": "Eres el Arquitecto de Software. Tu especialidad es diseñar la estructura técnica, diagramas y decidir las tecnologías.",
                "Developer Agent": "Eres el Desarrollador Principal. Te encargas de escribir código limpio y eficiente siguiendo el PRD.",
                "QA Agent": "Eres el Especialista en QA. Tu misión es probar el código, encontrar bugs y asegurar la calidad total.",
                "Advisor Agent": "Eres el Asesor de Producto. Ayudas a definir los requerimientos y la visión del negocio.",
                "Docs Agent": "Eres el Especialista en Documentación. Te encargas de Notion y de que todo el conocimiento sea accesible.",
                "DevOps Agent": "Eres el Ingeniero de DevOps. Gestionas la infraestructura, el despliegue y la automatización CI/CD."
            }
            final_instruction = role_instructions.get(display_name, final_instruction)

        agent = create_orchestrator()
        agent.instruction = final_instruction
        
        target_prompt = user_message

        session_service = InMemorySessionService()
        session = await session_service.create_session(app_name="claw3d-office", user_id=user_id_context or "claw3d_user")
        runner = Runner(agent=agent, app_name="claw3d-office", session_service=session_service)

        response_text = ""
        async for event in runner.run_async(
            user_id="claw3d_user",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=target_prompt)]),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                response_text = event.content.parts[0].text

        if not response_text:
             response_text = "El agente no pudo generar una respuesta en este momento."

        return {
            "id": f"tk-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": agent_id,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ]
        }
    except Exception as e:
        logger.error(f"Error en Claw3D Chat: {e}")
        return {"error": str(e)}, 500