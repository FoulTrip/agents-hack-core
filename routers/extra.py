from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from routers.auth import get_current_user
from core.db import db_manager

router = APIRouter(prefix="/api/kanban", tags=["kanban"])


@router.get("")
async def list_kanban(user: dict = Depends(get_current_user)):
    agents = await db_manager.client.agent.find_many(where={"userId": user["id"]})
    agent_ids = [a.id for a in agents]
    tasks = await db_manager.client.kanbantask.find_many(
        where={"agentId": {"in": agent_ids}}, order={"createdAt": "desc"}
    )
    return [{"id": t.id, "agentId": t.agentId, "title": t.title, "description": getattr(t, "description", None), "status": t.status, "priority": getattr(t, "priority", "medium"), "blockedBy": getattr(t, "blockedBy", []), "sessionRef": getattr(t, "sessionRef", None), "createdAt": t.createdAt.isoformat()} for t in tasks]


@router.post("")
async def create_kanban_task(body: dict, user: dict = Depends(get_current_user)):
    agents = await db_manager.client.agent.find_many(where={"userId": user["id"]})
    agent_ids = [a.id for a in agents]
    agent_id = body.get("agentId")
    if not agent_id or agent_id not in agent_ids:
        raise HTTPException(status_code=403, detail="Agent not found or not owned by user")
    task = await db_manager.client.kanbantask.create(data={"agentId": agent_id, "title": body.get("title", "Untitled"), "description": body.get("description"), "status": body.get("status", "todo"), "priority": body.get("priority", "medium"), "sessionRef": body.get("sessionRef")})
    return {"id": task.id, "status": "created"}


@router.patch("/{task_id}")
async def update_kanban_task(task_id: str, body: dict[str, Any], user: dict = Depends(get_current_user)):
    allowed = {k: v for k, v in body.items() if k in ("title", "description", "status", "priority", "blockedBy")}
    await db_manager.client.kanbantask.update(where={"id": task_id}, data=allowed)  # type: ignore[arg-type]
    return {"status": "updated"}


@router.delete("/{task_id}")
async def delete_kanban_task(task_id: str, user: dict = Depends(get_current_user)):
    await db_manager.client.kanbantask.delete(where={"id": task_id})
    return {"status": "deleted"}


skills_router = APIRouter(prefix="/api/skills", tags=["skills"])


@skills_router.get("")
async def list_skills(user: dict = Depends(get_current_user)):
    skills = await db_manager.client.skill.find_many(include={"agentSkills": True})
    return [{"id": s.id, "slug": s.slug, "name": s.name, "category": getattr(s, "category", None), "description": getattr(s, "description", None), "author": getattr(s, "author", None), "source": getattr(s, "source", "community"), "featured": getattr(s, "featured", False)} for s in skills]


@skills_router.post("/{skill_slug}/install")
async def install_skill(skill_slug: str, body: dict, user: dict = Depends(get_current_user)):
    agent_id = body.get("agentId")
    if not isinstance(agent_id, str):
        raise HTTPException(status_code=400, detail="agentId is required")
    skill = await db_manager.client.skill.find_unique(where={"slug": skill_slug})
    if not skill:
        skill = await db_manager.client.skill.create(data={"slug": skill_slug, "name": skill_slug.replace("-", " ").title(), "source": "community"})
    existing = await db_manager.client.agentskill.find_first(where={"agentId": agent_id, "skillId": skill.id})
    if existing:
        await db_manager.client.agentskill.update(where={"id": existing.id}, data={"installed": True, "enabled": True})
    else:
        await db_manager.client.agentskill.create(data={"agentId": agent_id, "skillId": skill.id, "installed": True, "enabled": True})
    return {"status": "installed"}


@skills_router.delete("/{skill_slug}/uninstall")
async def uninstall_skill(skill_slug: str, body: dict, user: dict = Depends(get_current_user)):
    agent_id = body.get("agentId")
    if not isinstance(agent_id, str):
        raise HTTPException(status_code=400, detail="agentId is required")
    skill = await db_manager.client.skill.find_unique(where={"slug": skill_slug})
    if skill:
        existing = await db_manager.client.agentskill.find_first(where={"agentId": agent_id, "skillId": skill.id})
        if existing:
            await db_manager.client.agentskill.update(where={"id": existing.id}, data={"installed": False, "enabled": False})
    return {"status": "uninstalled"}


hq_router = APIRouter(prefix="/api/hq", tags=["hq"])


@hq_router.get("/runs")
async def list_hq_runs(sessionId: str | None = None, user: dict = Depends(get_current_user)):
    where_clause: Any = None
    if sessionId:
        db_session = await db_manager.client.projectsession.find_unique(where={"sessionId": sessionId})
        if db_session:
            where_clause = {"sessionId": db_session.id}
    runs = await db_manager.client.hqrun.find_many(where=where_clause, order={"createdAt": "desc"}, take=50)
    return [{"id": r.id, "agentName": r.agentName, "agentRole": r.agentRole, "output": r.output[:500] + "..." if len(r.output) > 500 else r.output, "model": getattr(r, "model", "gemini-pro"), "toolCalls": getattr(r, "toolCalls", 0), "durationMs": getattr(r, "durationMs", 0), "success": getattr(r, "success", True), "createdAt": r.createdAt.isoformat()} for r in runs]


playbook_router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])


@playbook_router.get("")
async def list_playbooks(user: dict = Depends(get_current_user)):
    return await db_manager.client.playbook.find_many(order={"createdAt": "desc"})


@playbook_router.post("")
async def create_playbook(body: dict, user: dict = Depends(get_current_user)):
    import json
    pb = await db_manager.client.playbook.create(data={"name": body.get("name", "New Playbook"), "description": body.get("description"), "steps": json.dumps(body.get("steps", [])), "schedule": body.get("schedule"), "active": body.get("active", True)})
    return {"id": pb.id, "status": "created"}


memory_router = APIRouter(prefix="/api/agents", tags=["memory"])


@memory_router.get("/{agent_id}/memory")
async def get_agent_memory(agent_id: str, user: dict = Depends(get_current_user)):
    entries = await db_manager.client.agentmemory.find_many(where={"agentId": agent_id}, order={"updatedAt": "desc"})
    return [{"id": e.id, "key": e.key, "value": e.value, "source": getattr(e, "source", None), "updatedAt": e.updatedAt.isoformat()} for e in entries]


@memory_router.post("/{agent_id}/memory")
async def save_agent_memory(agent_id: str, body: dict[str, Any], user: dict = Depends(get_current_user)):
    key = body.get("key")
    if not isinstance(key, str):
        raise HTTPException(status_code=400, detail="key is required")
    existing = await db_manager.client.agentmemory.find_first(where={"agentId": agent_id, "key": key})
    if existing:
        await db_manager.client.agentmemory.update(where={"id": existing.id}, data={"value": body.get("value", ""), "source": body.get("source", "user")})
    else:
        await db_manager.client.agentmemory.create(data={"agentId": agent_id, "key": key, "value": body.get("value", ""), "source": body.get("source", "user")})
    return {"status": "saved"}