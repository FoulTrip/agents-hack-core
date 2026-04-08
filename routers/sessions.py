from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from uvicorn.protocols.utils import ClientDisconnected
from routers.auth import get_current_user
from core.db import db_manager
from core.logger import get_logger
from services.pipeline import session_manager, run_pipeline_with_callbacks, cleanup_external_resources

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["sessions"])


@router.post("/generate")
async def generate_project(request: dict, user: dict = Depends(get_current_user)):
    """Inicia un nuevo pipeline de generación de proyecto"""
    from models import PromptRequest
    import asyncio
    
    prompt_req = PromptRequest(**request)
    
    if prompt_req.session_id:
        session_id = prompt_req.session_id
        session_db = await session_manager.get_session(session_id)
        if not session_db: 
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
            
        messages = getattr(session_db, "messages", [])
        user_messages = [m for m in messages if m.role == "user"]
        resume_prompt = user_messages[0].content if user_messages else prompt_req.prompt
    else:
        session_id = await session_manager.create_session(
            user_id=user["id"],
            prompt=prompt_req.prompt,
            project_name=prompt_req.project_name
        )
        resume_prompt = prompt_req.prompt
        
        import json
        overall_layout = await db_manager.client.workspacelayout.find_unique(where={"wingId": user["id"]})
        if overall_layout:
            furniture = json.loads(overall_layout.furniture)
            sessions_count = await db_manager.client.projectsession.count(where={"userId": user["id"]})
            offset_x = sessions_count * 2000 
            wing_id = session_id
            wing_label = prompt_req.project_name or "UNTITLED"
            
            wing_furn = []
            wing_furn.append({"_uid": f"wall_n_{wing_id}", "type": "wall", "x": offset_x, "y": 0, "w": 1800, "h": 10})
            wing_furn.append({"_uid": f"wall_s_{wing_id}", "type": "wall", "x": offset_x, "y": 890, "w": 1800, "h": 10})
            wing_furn.append({"_uid": f"wall_w_{wing_id}", "type": "wall", "x": offset_x, "y": 0, "w": 10, "h": 900})
            wing_furn.append({"_uid": f"wall_e_{wing_id}", "type": "wall", "x": offset_x + 1790, "y": 0, "w": 10, "h": 900})
            
            wing_furn.append({
                "_uid": f"label_{wing_id}", 
                "type": "floor_logo", 
                "x": offset_x + 800, "y": 400, "w": 200, "h": 100, 
                "text": f"PROJECT: {wing_label[:15]}"
            })

            wing_furn.append({"_uid": f"mr_wall_v_{wing_id}", "type": "wall", "x": offset_x + 500, "y": 0, "w": 10, "h": 400})
            wing_furn.append({"_uid": f"mr_wall_h_{wing_id}", "type": "wall", "x": offset_x, "y": 400, "w": 400, "h": 10})
            wing_furn.append({"_uid": f"meeting_table_{wing_id}", "type": "round_table", "x": offset_x + 150, "y": 150, "w": 200, "h": 200})

            for i in range(6):
                row = i // 3
                col = i % 3
                desk_x = offset_x + 700 + col * 350
                desk_y = 150 + row * 350
                wing_furn.append({"_uid": f"{wing_id}:desk_{i}", "type": "desk_cubicle", "x": desk_x, "y": desk_y, "facing": 180})
                wing_furn.append({"_uid": f"chair_{wing_id}_{i}", "type": "chair", "x": desk_x + 35, "y": desk_y + 60, "facing": 0})
                wing_furn.append({"_uid": f"comp_{wing_id}_{i}", "type": "computer", "x": desk_x + 35, "y": desk_y + 15, "facing": 0})
                
            furniture.extend(wing_furn)
            
            await db_manager.client.workspacelayout.update(
                where={"wingId": user["id"]},
                data={"furniture": json.dumps(furniture), "offsetX": offset_x}
            )

    asyncio.create_task(run_pipeline_with_callbacks(session_id, resume_prompt, prompt_req.webhook_url))
    
    if prompt_req.agentTasks:
        from app_state import agent_task_cache
        agent_task_cache[session_id] = prompt_req.agentTasks
    
    return {"session_id": session_id, "status": "started", "websocket_url": f"/ws/{session_id}"}


@router.get("/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    """Lista todas las sesiones del usuario"""
    sessions = await session_manager.list_user_sessions(user["id"])
    return sessions


@router.get("/status/{session_id}")
async def get_status(session_id: str):
    """Obtiene el estado de una sesión"""
    session = await session_manager.get_session(session_id)
    if not session: raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return session


@router.post("/approve/{session_id}")
async def approve_phase(session_id: str, user: dict = Depends(get_current_user)):
    """Aprueba la fase actual para que el pipeline continúe"""
    session = await db_manager.client.projectsession.find_unique(where={"sessionId": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    if str(session.userId) != user["id"]:
        raise HTTPException(status_code=403, detail="No autorizado")

    # Cambiamos estado de la sesión a 'approved' para que el loop de pipeline.py despierte
    await session_manager.update_session(session_id, status="approved")
    
    await session_manager.broadcast_to_session(session_id, {
        "type": "approved",
        "message": "✅ Aprobación humana recibida. Continuando ejecución..."
    })
    
    return {"status": "success", "message": "Fase aprobada"}


@router.post("/reject/{session_id}")
async def reject_phase(session_id: str, feedback: dict, user: dict = Depends(get_current_user)):
    """Rechaza la fase actual y envía feedback para re-ejecución"""
    session = await db_manager.client.projectsession.find_unique(where={"sessionId": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    if str(session.userId) != user["id"]:
        raise HTTPException(status_code=403, detail="No autorizado")

    comment = feedback.get("message", "No se proporcionó feedback específico.")
    
    # Añadimos el feedback como un mensaje del usuario para el contexto del agente
    await session_manager.add_message(session_id, "user", f"SOLICITUD DE CAMBIOS: {comment}")
    
    # Cambiamos el estado para que pipeline.py reaccione
    await session_manager.update_session(session_id, status="rejected")
    
    await session_manager.broadcast_to_session(session_id, {
        "type": "rejected",
        "message": f"❌ Cambios solicitados: {comment}"
    })
    
    return {"status": "success", "message": "Feedback enviado"}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    """Elimina una sesión y todos sus datos asociados"""
    session = await db_manager.client.projectsession.find_unique(
        where={"sessionId": session_id},
        include={"notionPages": True, "githubRepos": True}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    if str(session.userId) != user["id"]:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    try:
        await cleanup_external_resources(session, user["id"])
    except Exception as e:
        logger.error(f"Error durante la limpieza externa: {e}")

    await db_manager.client.message.delete_many(where={"sessionId": session.id})
    await db_manager.client.notionpage.delete_many(where={"sessionId": session.id})
    await db_manager.client.githubrepo.delete_many(where={"sessionId": session.id})
    await db_manager.client.artifact.delete_many(where={"sessionId": session.id})
    await db_manager.client.agentactivity.delete_many(where={"sessionId": session.id})
    await db_manager.client.hqrun.delete_many(where={"sessionId": session.id})
    try:
        await db_manager.client.sessiondecision.delete_many(where={"sessionId": session.id})  # type: ignore
    except Exception:
        pass
    try:
        await db_manager.client.pipelinelog.delete_many(where={"sessionId": session.id})  # type: ignore
    except Exception:
        pass
    await db_manager.client.projectsession.delete(where={"id": session.id})
    
    logger.info(f"🗑️ Sesión eliminada: {session_id} por usuario {user['id']}")
    return {"status": "success", "message": "Sesión eliminada"}


@router.get("/sessions/{session_id}/logs")
async def get_session_logs(session_id: str, limit: int = 500, user: dict = Depends(get_current_user)):
    """Recupera todos los logs del pipeline para replay en el frontend"""
    session = await db_manager.client.projectsession.find_unique(where={"sessionId": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    if str(session.userId) != user["id"]:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    logs = await session_manager.get_pipeline_logs(session_id, limit=limit)
    return [
        {
            "id": str(log.id),
            "type": log.type,
            "message": log.message,
            "detail": log.detail,
            "level": log.level,
            "phaseId": log.phaseId,
            "phaseLabel": log.phaseLabel,
            "agentName": log.agentName,
            "agentRole": log.agentRole,
            "metadata": log.metadata,
            "createdAt": log.createdAt.isoformat() if log.createdAt else None
        }
        for log in logs
    ]



@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket para actualizaciones en tiempo real"""
    logger.info(f"WebSocket connection attempt for session: {session_id}")
    
    try:
        await websocket.accept()
        logger.info(f"WebSocket accepted for session: {session_id}")
    except Exception as e:
        logger.error(f"Failed to accept WebSocket: {e}")
        return
    
    try:
        session = await session_manager.get_session(session_id)
        if not session:
            logger.warning(f"Session not found: {session_id}")
            await websocket.send_json({"type": "error", "message": "Sesión no encontrada"})
            await websocket.close()
            return

        user_id_ws = websocket.query_params.get("userId")
        logger.info(f"Session found, connecting WS for user: {user_id_ws}")
        
        session_manager.add_websocket(session_id, websocket, user_id=user_id_ws)
        
        def serialize_message(msg) -> dict:
            return {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "createdAt": msg.createdAt.isoformat() if msg.createdAt else None
            }

        def serialize_activity(act) -> dict:
            return {
                "id": str(act.id),
                "agentName": getattr(act, "agentName", "Unknown"),
                "agentRole": getattr(act, "agentRole", "Unknown"),
                "taskDescription": getattr(act, "taskDescription", ""),
                "status": getattr(act, "status", "unknown"),
                "model": getattr(act, "model", None),
                "startTime": act.startTime.isoformat() if hasattr(act, "startTime") and act.startTime else None,
                "endTime": act.endTime.isoformat() if hasattr(act, "endTime") and act.endTime else None,
                "durationMs": getattr(act, "durationMs", None),
                "costEstimate": getattr(act, "costEstimate", 0)
            }

        def serialize_notion(page) -> dict:
            return {
                "id": str(page.id),
                "title": page.title,
                "url": page.url,
                "pageId": page.pageId
            }

        def serialize_github(repo) -> dict:
            return {
                "name": repo.name,
                "url": repo.url,
                "fullName": repo.fullName
            }

        def serialize_artifact(art) -> dict:
            return {
                "id": str(art.id),
                "type": art.type,
                "title": art.title,
                "url": art.url,
                "content": art.content,
                "createdAt": art.createdAt.isoformat() if art.createdAt else None
            }

        try:
            # Extraemos el último repo y página para conveniencia del frontend
            latest_repo = session.githubRepos[-1].url if hasattr(session, "githubRepos") and session.githubRepos else None
            latest_notion = {
                "url": session.notionPages[-1].url,
                "title": session.notionPages[-1].title
            } if hasattr(session, "notionPages") and session.notionPages else None

            # Recuperar logs persistidos para replay
            persisted_logs = await session_manager.get_pipeline_logs(session_id, limit=500)
            serialized_logs = [
                {
                    "type": log.type,
                    "message": log.message,
                    "level": log.level,
                    "phaseId": log.phaseId,
                    "phaseLabel": log.phaseLabel,
                    "agentName": log.agentName,
                    "agentRole": log.agentRole,
                    "createdAt": log.createdAt.isoformat() if log.createdAt else None
                }
                for log in persisted_logs
            ]

            # Consolidar documentos de Notion y Artefactos locales
            all_docs = []
            if hasattr(session, "notionPages") and session.notionPages:
                all_docs.extend([serialize_notion(p) for p in session.notionPages])
            if hasattr(session, "artifacts") and session.artifacts:
                all_docs.extend([serialize_artifact(a) for a in session.artifacts])

            state_payload = {
                "type": "session_state",
                "session_id": session_id,
                "status": session.status,
                "currentPhase": getattr(session, "currentPhase", None),
                "completedPhases": getattr(session, "completedPhases", []),
                "history": [serialize_message(m) for m in session.messages] if hasattr(session, "messages") and session.messages else [],
                "agentActivities": [serialize_activity(a) for a in session.agentActivities] if hasattr(session, "agentActivities") and session.agentActivities else [],
                "docs": all_docs,
                "githubRepos": [serialize_github(r) for r in session.githubRepos] if hasattr(session, "githubRepos") and session.githubRepos else [],
                "repoUrl": latest_repo,
                "notionDoc": latest_notion,
                "pipelineLogs": serialized_logs
            }
            await websocket.send_json(state_payload)
            logger.info(f"Initial state sent to websocket for session: {session_id} ({len(serialized_logs)} logs replayed, status: {session.status})")
        except (WebSocketDisconnect, ClientDisconnected) as e:
            logger.error(f"WebSocket disconnected during initial state send: {e}")
            session_manager.remove_websocket(session_id, websocket)
            return
        except Exception as e:
            logger.error(f"Error preparing or sending initial state: {e}", exc_info=True)
            # Intentar enviar un estado básico si el complejo falló
            try:
                await websocket.send_json({
                    "type": "session_state",
                    "session_id": session_id,
                    "status": session.status if 'session' in locals() else "unknown",
                    "error": f"Error parcial al recuperar datos: {str(e)}"
                })
            except (WebSocketDisconnect, ClientDisconnected):
                session_manager.remove_websocket(session_id, websocket)
                return
            except: pass

        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected normally for session: {session_id}")
                break
            except Exception as e:
                logger.error(f"Error in websocket receive: {e}")
                break

    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        logger.info(f"Cleaning up websocket for session: {session_id}")
        session_manager.remove_websocket(session_id, websocket)