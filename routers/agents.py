import json
from typing import Any, List, Optional, cast
from fastapi import APIRouter, Depends, HTTPException
from routers.auth import get_current_user
from core.db import db_manager
from core.logger import get_logger
from models import AgentModel, DEFAULT_AGENTS, AgentRoleDefinitionModel
from services.pipeline import session_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/api/user/agents", tags=["agents"])


@router.get("", response_model=List[AgentModel])
async def list_user_agents(user_token: dict = Depends(get_current_user)):
    user_id = user_token["id"]
    agents = await db_manager.client.agent.find_many(
        where={"userId": user_id},
        order={"order": "asc"}
    )
    
    if not agents:
        logger.info(f"Creando agentes por defecto para el usuario {user_id}")
        for def_agent in DEFAULT_AGENTS:
            agent_data = {k: v for k, v in def_agent.items() if k != "avatarProfile"}
            avatar_profile = def_agent.get("avatarProfile")
            create_data: dict = {"userId": user_id, **agent_data}
            if avatar_profile is not None:
                create_data["avatarProfile"] = json.dumps(avatar_profile)
            await db_manager.client.agent.create(data=cast(Any, create_data))
        agents = await db_manager.client.agent.find_many(
            where={"userId": user_id},
            order={"order": "asc"}
        )
    
    def to_model(a) -> AgentModel:
        # Use getattr with default to handle cases where DB has None for new fields
        return AgentModel(
            id=str(a.id),
            name=a.name,
            role=a.role,
            icon=a.icon,
            color=a.color,
            description=a.description,
            model=getattr(a, "model", "gemini-3-flash-preview") or "gemini-3-flash-preview",
            avatarUrl=getattr(a, "avatarUrl", None),
            order=a.order,
            active=a.active,
            tools=a.tools,
            connectors=a.connectors,
            
            # Claw3D Persona
            vibe=getattr(a, "vibe", "Sharp and helpful") or "Sharp and helpful",
            emoji=getattr(a, "emoji", "🤖") or "🤖",
            personality=getattr(a, "personality", None),
            context=getattr(a, "context", None),
            guidelines=getattr(a, "guidelines", None),
            boundaries=getattr(a, "boundaries", "No realizar acciones destructivas.") or "No realizar acciones destructivas.",
            operatingInstructions=getattr(a, "operatingInstructions", "Analiza paso a paso antes de actuar.") or "Analiza paso a paso antes de actuar.",
            
            # Big Five
            openness=getattr(a, "openness", 0.8) if getattr(a, "openness", None) is not None else 0.8,
            conscientiousness=getattr(a, "conscientiousness", 0.9) if getattr(a, "conscientiousness", None) is not None else 0.9,
            extraversion=getattr(a, "extraversion", 0.6) if getattr(a, "extraversion", None) is not None else 0.6,
            agreeableness=getattr(a, "agreeableness", 0.7) if getattr(a, "agreeableness", None) is not None else 0.7,
            neuroticism=getattr(a, "neuroticism", 0.2) if getattr(a, "neuroticism", None) is not None else 0.2,

            # Claw3D Office Social
            status=getattr(a, "status", "idle") or "idle",
            avatarProfile=getattr(a, "avatarProfile", {}) or {},
            officeDesk=getattr(a, "officeDesk", None),
            officeWing=getattr(a, "officeWing", "Core") or "Core",
            officeFloor=getattr(a, "officeFloor", 1) if getattr(a, "officeFloor", None) is not None else 1,
            avatarStyle=getattr(a, "avatarStyle", "pixel") or "pixel",
            socialTone=getattr(a, "socialTone", "Professional") or "Professional",
            standupBehavior=getattr(a, "standupBehavior", "Participant") or "Participant",
            computerType=getattr(a, "computerType", "high-end-pc") or "high-end-pc",
            
            # LLM
            temperature=getattr(a, "temperature", 0.7) if getattr(a, "temperature", None) is not None else 0.7,
            maxTokens=getattr(a, "maxTokens", 4096) if getattr(a, "maxTokens", None) is not None else 4096,
            roleDefinitionId=getattr(a, "roleDefinitionId", None)
        )

    return [to_model(a) for a in agents]


@router.post("", response_model=AgentModel)
async def create_agent(agent: AgentModel, user_token: dict = Depends(get_current_user)):
    data = agent.model_dump(exclude={"id", "userId"})
    data["user"] = {"connect": {"id": user_token["id"]}}
    new_agent = await db_manager.client.agent.create(data=cast(Any, data))
    return AgentModel(**{**new_agent.__dict__, "id": str(new_agent.id)})


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, agent: AgentModel, user_token: dict = Depends(get_current_user)):
    existing = await db_manager.client.agent.find_unique(where={"id": agent_id})
    if not existing or str(getattr(existing, "userId", "")) != user_token["id"]:
        raise HTTPException(status_code=403, detail="No autorizado")
        
    data = agent.model_dump(exclude={"id", "userId", "currentTask"})
    await db_manager.client.agent.update(where={"id": agent_id}, data=cast(Any, data))
    return {"status": "success"}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, user_token: dict = Depends(get_current_user)):
    existing = await db_manager.client.agent.find_unique(where={"id": agent_id})
    if not existing or str(getattr(existing, "userId", "")) != user_token["id"]:
        raise HTTPException(status_code=403, detail="No autorizado")

    await db_manager.client.agent.delete(where={"id": agent_id})
    return {"status": "success"}


@router.get("/live")
async def list_live_agents(user_token: dict = Depends(get_current_user)):
    """Returns agents with their latest activity if available."""
    user_id = user_token["id"]
    agents = await db_manager.client.agent.find_many(
        where={"userId": user_id},
        order={"order": "asc"}
    )
    
    # Get latest activity for each agent
    live_data = []
    for a in agents:
        latest_activity = await db_manager.client.agentactivity.find_first(
            where={"agentName": a.name}, 
            order={"createdAt": "desc"}
        )
        
        live_data.append({
            "id": str(a.id),
            "name": a.name,
            "role": a.role,
            "emoji": getattr(a, "emoji", "🤖") or "🤖",
            "color": a.color,
            "status": getattr(a, "status", "idle") or "idle",
            "officeDesk": getattr(a, "officeDesk", ""),
            "officeWing": getattr(a, "officeWing", "Core"),
            "activity": {
                "task": getattr(latest_activity, "taskDescription", "Idle") if latest_activity else "No active task",
                "thought": getattr(latest_activity, "thoughtProcess", "Waiting for input...") if latest_activity else "Idle...",
                "lastSeen": latest_activity.createdAt.isoformat() if latest_activity else None
            }
        })
        
    return live_data


@router.get("/desks")
async def get_office_desks(user_token: dict = Depends(get_current_user)):
    """Returns desks from the user's saved office layout, marking which are occupied."""
    from models import DEFAULT_OFFICE_LAYOUT
    
    # Load agent assignments
    agents = await db_manager.client.agent.find_many(
        where={"userId": user_token["id"]},
        order={"order": "asc"}
    )
    # Map deskId -> agent name for occupied check
    occupied: dict[str, str] = {}
    for a in agents:
        desk = getattr(a, "officeDesk", None)
        if desk:
            occupied[desk] = a.name

    # Try to load the user's saved layout; fall back to default
    user = await db_manager.client.user.find_unique(where={"id": user_token["id"]})
    layout = DEFAULT_OFFICE_LAYOUT
    raw = getattr(user, "officeDefaults", None) if user else None
    if raw:
        try:
            layout = json.loads(raw)
        except Exception:
            pass

    desks = layout.get("desks", [])
    return [
        {
            **desk,
            "occupied": desk["id"] in occupied,
            "occupantName": occupied.get(desk["id"])
        }
        for desk in desks
    ]


internal_router = APIRouter(prefix="/api/internal", tags=["internal"])


@internal_router.get("/agents", response_model=List[AgentModel])
async def list_internal_agents(sessionId: Optional[str] = None):
    from app_state import agent_task_cache
    
    task_map: dict[str, str] = {}
    if sessionId and sessionId in agent_task_cache:
        for item in agent_task_cache[sessionId]:
            task_map[item.get("role", "")] = item.get("task", "")

    def build_agent_model(a, task_override: Optional[str] = None) -> AgentModel:
        def g(attr, default=None):
            val = getattr(a, attr, default) if hasattr(a, attr) else a.get(attr, default)
            return val if val is not None else default

        return AgentModel(
            id=str(g("id")),
            name=g("name"),
            role=g("role"),
            icon=g("icon", "Brain"),
            color=g("color", "#6366F1"),
            description=g("description"),
            model=g("model", "gemini-3-flash-preview"),
            avatarUrl=g("avatarUrl"),
            
            vibe=g("vibe", "Sharp and helpful"),
            emoji=g("emoji", "🤖"),
            personality=g("personality"),
            context=g("context"),
            guidelines=g("guidelines"),
            boundaries=g("boundaries", "No realizar acciones destructivas."),
            operatingInstructions=g("operatingInstructions", "Analiza paso a paso antes de actuar."),
            
            openness=g("openness", 0.8),
            conscientiousness=g("conscientiousness", 0.9),
            extraversion=g("extraversion", 0.6),
            agreeableness=g("agreeableness", 0.7),
            neuroticism=g("neuroticism", 0.2),

            status=g("status", "idle"),
            avatarProfile=g("avatarProfile", {}),
            officeDesk=g("officeDesk"),
            officeWing=g("officeWing", "Core"),
            officeFloor=g("officeFloor", 1),
            avatarStyle=g("avatarStyle", "pixel"),
            socialTone=g("socialTone", "Professional"),
            standupBehavior=g("standupBehavior", "Participant"),
            computerType=g("computerType", "high-end-pc"),
            
            temperature=g("temperature", 0.7),
            maxTokens=g("maxTokens", 4096),
            
            order=g("order", 0),
            active=g("active", True),
            tools=g("tools", []),
            connectors=g("connectors", []),
            currentTask=task_override,
        )

    if sessionId:
        session = await db_manager.client.projectsession.find_unique(where={"sessionId": sessionId})
        if session:
            agents = await db_manager.client.agent.find_many(where={"userId": session.userId}, order={"order": "asc"})
            return [build_agent_model(a, task_map.get(a.role)) for a in agents]
    
    agents = await db_manager.client.agent.find_many(order={"order": "asc"})
    if not agents:
        return [build_agent_model(a, task_map.get(a.get('role', ''))) for a in DEFAULT_AGENTS]
    
    first_user_id = agents[0].userId
    user_agents = [a for a in agents if a.userId == first_user_id]
    return [build_agent_model(a, task_map.get(a.role)) for a in user_agents]


@internal_router.post("/activity-report")
async def activity_report(report: dict):
    from models import ActivityReport
    r = ActivityReport(**report)
    content = ""
    if r.action == "talk" and r.message: content = f"💬 (to everyone): {r.message}"
    elif r.action == "work" and r.thought: content = f"💻 Trabajando: {r.thought}"
    elif r.thought: content = f"💡 Pensando: {r.thought}"
    else: content = f"👉 Acción: {r.action}"

    await session_manager.add_message(r.sessionId, "assistant", f"[{r.agentName}] {content}")
    await session_manager.broadcast_to_session(r.sessionId, {
        "type": "phase_start",
        "logs": [f"🤖 AGENTE [{r.agentName}]: {content}"]
    })
    return {"status": "ok"}


@router.get("/roles/generate-prompt")
async def generate_role_prompt(name: str, description: str = ""):
    """Generates a professional system prompt for an agent role using AI."""
    from services.ai import ai_service
    prompt = f"""
    Eres un experto en orquestación de Agentes de Software Factory.
    Genera un 'System Prompt Template' para un rol de agente con los siguientes detalles:
    Nombre: {name}
    Descripción: {description}

    El prompt debe estar en ESPAÑOL, ser profesional, incluir objetivos claros, 
    guidelines de comportamiento y restricciones. 
    Responde ÚNICAMENTE con el texto del prompt, sin explicaciones.
    """
    try:
        response = await ai_service.generate_text(prompt, model="gemini-3-flash-preview")
        return {"prompt": response.strip()}
    except Exception as e:
        logger.error(f"Error generating AI prompt: {e}")
        return {"prompt": f"Actúa como un {name} experto. Tu objetivo es {description}."}


# --- Role Definitions Endpoints ---

@router.get("/roles", response_model=List[AgentRoleDefinitionModel])
async def list_role_definitions(user_token: dict = Depends(get_current_user)):
    user_id = user_token["id"]
    from models import DEFAULT_ROLES
    
    # Check existing roles
    roles = await db_manager.client.agentroledefinition.find_many(
        where={"userId": user_id}
    )
    
    # If any default role is missing, or needs a prompt update
    existing_slugs = {r.slug: r for r in roles}
    needs_re_fetch = False
    
    for def_role in DEFAULT_ROLES:
        slug = def_role["slug"]
        if slug not in existing_slugs:
            role_data = {**def_role, "isDefault": True, "user": {"connect": {"id": user_id}}}
            await db_manager.client.agentroledefinition.create(data=cast(Any, role_data))
            needs_re_fetch = True
        else:
            # Check if it's a default role and lacks a prompt
            existing = existing_slugs[slug]
            if existing.isDefault and (not existing.systemPrompt or len(existing.systemPrompt) < 5):
                await db_manager.client.agentroledefinition.update(
                    where={"id": existing.id},
                    data=cast(Any, {"systemPrompt": def_role["systemPrompt"]})
                )
                needs_re_fetch = True
    
    if needs_re_fetch:
        roles = await db_manager.client.agentroledefinition.find_many(
            where={"userId": user_id}
        )
        
    return [AgentRoleDefinitionModel(**{**r.__dict__, "id": str(r.id)}) for r in roles]

@router.post("/roles", response_model=AgentRoleDefinitionModel)
async def create_role_definition(role: AgentRoleDefinitionModel, user_token: dict = Depends(get_current_user)):
    data = role.model_dump(exclude={"id", "userId", "createdAt"})
    data["user"] = {"connect": {"id": user_token["id"]}}
    new_role = await db_manager.client.agentroledefinition.create(data=cast(Any, data))
    return AgentRoleDefinitionModel(**{**new_role.__dict__, "id": str(new_role.id)})

@router.patch("/roles/{role_id}")
async def update_role_definition(role_id: str, role: AgentRoleDefinitionModel, user_token: dict = Depends(get_current_user)):
    existing = await db_manager.client.agentroledefinition.find_unique(where={"id": role_id})
    if not existing or str(getattr(existing, "userId", "")) != user_token["id"]:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    data = role.model_dump(exclude={"id", "userId", "createdAt", "isDefault"})
    await db_manager.client.agentroledefinition.update(where={"id": role_id}, data=cast(Any, data))
    return {"status": "success"}

@router.delete("/roles/{role_id}")
async def delete_role_definition(role_id: str, user_token: dict = Depends(get_current_user)):
    existing = await db_manager.client.agentroledefinition.find_unique(where={"id": role_id})
    if not existing or str(getattr(existing, "userId", "")) != user_token["id"]:
        raise HTTPException(status_code=403, detail="No autorizado")

    await db_manager.client.agentroledefinition.delete(where={"id": role_id})
    return {"status": "success"}