import asyncio
import re
from typing import Optional
from core.db import db_manager
from core.context import set_user_context
from core.logger import get_logger
from models.SessionManager import SessionManager
from services.budget_guardian import BudgetGuardian, calculate_activity_cost

logger = get_logger(__name__)

session_manager = SessionManager()


def _normalize_repo_full_name(repo: str | None) -> str | None:
    if not repo:
        return None
    normalized = str(repo).strip()
    normalized = normalized.replace("https://github.com/", "").replace("http://github.com/", "")
    normalized = normalized.strip().strip("/")
    if normalized.lower().endswith(".git"):
        normalized = normalized[:-4]
    return normalized or None


async def _build_phase_agent(
    agent_role: str,
    user_agents: list,
    preferred_model: str,
    user_id: str,
    session_id: str,
):
    """Devuelve el agente especializado para la fase actual.

    Esto evita depender de que el orquestador delegue correctamente en cada vuelta.
    """
    if agent_role == "requirements_agent":
        logger.debug(f"[session={session_id}] Resolviendo agente de fase: role={agent_role}")
        from agents.requirements.agent import create_requirements_agent
        return await create_requirements_agent(user_agents, model=preferred_model, user_id=user_id, session_id=session_id)
    if agent_role == "architecture_agent":
        logger.debug(f"[session={session_id}] Resolviendo agente de fase: role={agent_role}")
        from agents.architecture.agent import create_architecture_agent
        return await create_architecture_agent(user_agents, model=preferred_model, user_id=user_id, session_id=session_id)
    if agent_role == "development_agent":
        logger.debug(f"[session={session_id}] Resolviendo agente de fase: role={agent_role}")
        from agents.development.agent import create_development_agent
        return await create_development_agent(user_agents, model=preferred_model, user_id=user_id, session_id=session_id)
    if agent_role == "qa_agent":
        logger.debug(f"[session={session_id}] Resolviendo agente de fase: role={agent_role}")
        from agents.qa.agent import create_qa_agent
        return await create_qa_agent(user_agents, model=preferred_model, user_id=user_id, session_id=session_id)
    if agent_role == "documentation_agent":
        logger.debug(f"[session={session_id}] Resolviendo agente de fase: role={agent_role}")
        from agents.documentation.agent import create_documentation_agent
        return await create_documentation_agent(user_agents, model=preferred_model, user_id=user_id, session_id=session_id)
    if agent_role == "devops_agent":
        logger.debug(f"[session={session_id}] Resolviendo agente de fase: role={agent_role}")
        from agents.devops.agent import create_devops_agent
        return await create_devops_agent(user_agents, model=preferred_model, user_id=user_id, session_id=session_id)

    # Fallback: para roles personalizados no estándar, mantener al orquestador.
    logger.warning(f"[session={session_id}] Rol de agente no estándar '{agent_role}', usando Orchestrator como fallback")
    from agents.orchestrator.agent import create_orchestrator
    return await create_orchestrator(
        user_agents=user_agents,
        model=preferred_model,
        user_id=user_id,
        session_id=session_id
    )

async def extract_and_link_artifacts(session_id: str, text: str, user_config: dict | None = None):
    """Extrae enlaces de Notion y GitHub y los guarda en la DB"""
    last_notion_url = None
    notion_links = re.findall(r'https://(?:www\.)?notion\.so/([A-Za-z0-9-]+)', text)
    github_links = re.findall(r'https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)', text)
    logger.debug(
        f"[session={session_id}] Artifact scan: notion_links={len(notion_links)} github_links={len(github_links)} text_len={len(text or '')}"
    )
    for link in notion_links:
        last_notion_url = f"https://www.notion.so/{link}"
        page_id = link.split("-")[-1]
        await session_manager.link_notion_page(
            session_id=session_id,
            title="Página Generada",
            url=last_notion_url,
            page_id=page_id
        )
    
    repo_url = None
    for repo in github_links:
        repo_full_name = _normalize_repo_full_name(repo)
        if not repo_full_name:
            continue
        repo_url = f"https://github.com/{repo_full_name}"
        await session_manager.link_github_repo(
            session_id=session_id,
            name=repo_full_name.split('/')[-1],
            url=repo_url,
            full_name=repo_full_name
        )
    if repo_url:
        logger.info(f"🚀 Repositorio detectado y vinculado: {repo_url}")
    if last_notion_url:
        logger.info(f"📄 Documento Notion detectado: {last_notion_url}")
        
    return {"repoUrl": repo_url, "notionDoc": {"url": last_notion_url, "title": "Página de la Fase"} if last_notion_url else None}


async def cleanup_external_resources(session, user_id: str):
    """Elimina repositorios de GitHub y archiva páginas de Notion asociados a una sesión."""
    logger.info(f"🧹 Iniciando limpieza externa para sesión {session.sessionId}")
    
    user = await db_manager.client.user.find_unique(where={"id": user_id})
    if not user:
        return

    github_token = getattr(user, "githubToken", None)
    notion_token = getattr(user, "notionToken", None)

    import aiohttp

    async with aiohttp.ClientSession() as http_session:
        if github_token:
            for repo in getattr(session, "githubRepos", []):
                try:
                    logger.info(f"🗑️ Eliminando repo GitHub: {repo.fullName}")
                    headers = {
                        "Authorization": f"token {github_token}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                    async with http_session.delete(f"https://api.github.com/repos/{repo.fullName}", headers=headers) as resp:
                        if resp.status == 204:
                            logger.info(f"✅ Repo {repo.fullName} eliminado")
                        else:
                            text = await resp.text()
                            logger.warning(f"⚠️ Falló borrado de GitHub ({resp.status}): {text}")
                except Exception as e:
                    logger.error(f"❌ Error borrando GitHub: {e}")

        if notion_token:
            for page in getattr(session, "notionPages", []):
                try:
                    logger.info(f"🗑️ Archivando página Notion: {page.pageId}")
                    headers = {
                        "Authorization": f"Bearer {notion_token}",
                        "Content-Type": "application/json",
                        "Notion-Version": "2022-06-28"
                    }
                    data = {"archived": True}
                    async with http_session.patch(f"https://api.notion.com/v1/pages/{page.pageId}", headers=headers, json=data) as resp:
                        if resp.status == 200:
                            logger.info(f"✅ Página Notion {page.pageId} archivada")
                        else:
                            text = await resp.text()
                            logger.warning(f"⚠️ Falló archivado de Notion ({resp.status}): {text}")
                except Exception as e:
                    logger.error(f"❌ Error archivando Notion: {e}")


async def run_pipeline_with_callbacks(
    session_id: str,
    prompt: str,
    webhook_url: Optional[str] = None
):
    """Ejecuta el pipeline con callbacks y guarda historial en MongoDB"""
    from datetime import datetime
    from google.adk.sessions import InMemorySessionService
    run_id = f"{session_id[:8]}-{int(datetime.now().timestamp())}"
    current_phase_id: int | None = None
    current_phase_label: str | None = None
    current_phase_role: str | None = None
    logger.info(f"[run={run_id}] Pipeline start requested for session={session_id}")
    
    db_session = await session_manager.get_session(session_id)
    if not db_session:
        logger.error(f"[run={run_id}] No se encontró la sesión {session_id}")
        return
        
    completed_phases = getattr(db_session, "completedPhases", [])
    user_id_internal = str(getattr(db_session, "userId", "generic_user"))
    logger.info(
        f"[run={run_id}] Session loaded user={user_id_internal} completed_phases={completed_phases} webhook={'yes' if webhook_url else 'no'}"
    )
    
    await session_manager.update_session(session_id, status="running")
    
    messages = getattr(db_session, "messages", [])
    if not messages:
        await session_manager.add_message(session_id, "user", prompt)
    
    await session_manager.broadcast_to_session(session_id, {
        "type": "pipeline_start",
        "session_id": session_id,
        "prompt": prompt,
        "resumed": len(completed_phases) > 0
    })
    await session_manager.add_pipeline_log(
        session_id=session_id, type="pipeline_start",
        message=f"🚀 Pipeline iniciado{' (retomado)' if completed_phases else ''}. Prompt: {prompt[:100]}",
        metadata={"resumed": len(completed_phases) > 0, "prompt_length": len(prompt)}
    )
    
    try:
        user_db = await db_manager.client.user.find_unique(where={"id": user_id_internal})
        logger.debug(f"[run={run_id}] User config loaded: exists={'yes' if user_db else 'no'}")
        user_language = getattr(user_db, "language", "es") or "es"
        language_name = "ESPAÑOL" if user_language == "es" else "INGLÉS"

        user_config = {}
        if user_db:
            if user_db.githubToken:
                user_config["githubToken"] = user_db.githubToken
            if user_db.notionToken:
                user_config["notionToken"] = user_db.notionToken
            if user_db.notionWorkspaceId:
                user_config["notionWorkspaceId"] = user_db.notionWorkspaceId
        
        set_user_context(user_id_internal, session_id, user_config)

        user_agents = await db_manager.client.agent.find_many(
            where={"userId": user_id_internal, "active": True},
            order={"order": "asc"}
        )
        logger.info(f"[run={run_id}] Active agents found={len(user_agents)}")
        
        preferred_model = getattr(user_db, "preferredModel", "gemini-flash") or "gemini-flash"
        logger.info(f"[run={run_id}] Preferred model={preferred_model}")
        session_service = InMemorySessionService()
        
        if not user_agents:
            phases = [
                ("requirements_agent", "Requirements", "FASE 1 — Generando requerimientos...", ["notion"]),
                ("architecture_agent", "Architecture", "FASE 2 — Generando arquitectura...", ["notion"]),
                ("development_agent", "Development", "FASE 3 — Generando código y repositorio...", ["github", "notion"]),
                ("qa_agent", "QA & Tests", "FASE 4a — Generando tests...", ["github", "notion"]),
                ("documentation_agent", "Docs", "FASE 4b — Generando documentación...", ["github", "notion"]),
                ("devops_agent", "DevOps", "FASE 5 — Configurando infraestructura DevOps...", ["github", "notion"]),
            ]
        else:
            phases = [(a.role, a.name, f"PROCESANDO: {a.name}...", a.connectors) for a in user_agents]
        logger.info(
            f"[run={run_id}] Pipeline plan phases={len(phases)} labels={[p[1] for p in phases]}"
        )
        
        responses = {}
        locked_repo_full_name: str | None = None
        try:
            existing_repos = getattr(db_session, "githubRepos", []) or []
            if existing_repos:
                locked_repo_full_name = _normalize_repo_full_name(getattr(existing_repos[-1], "fullName", None))
                if locked_repo_full_name:
                    logger.info(f"[run={run_id}] Reusing existing repo from session state: {locked_repo_full_name}")
        except Exception:
            pass
        
        if completed_phases:
            ass_messages = await db_manager.client.message.find_many(
                where={"sessionId": getattr(db_session, "id"), "role": "assistant"},
                order={"createdAt": "asc"}
            )
            for i, msg in enumerate(ass_messages):
                raw_content = msg.content
                content = re.sub(r"^Fase \d+ \(.+\) completada:\n", "", raw_content)
                responses[i] = content

        for i, (agent_role, label, header, connectors) in enumerate(phases):
            phase_id = i + 1
            current_phase_id = phase_id
            current_phase_label = label
            current_phase_role = agent_role
            logger.info(
                f"[run={run_id}] Enter phase={phase_id} label={label} role={agent_role} connectors={connectors}"
            )
            
            if phase_id in completed_phases:
                logger.info(f"[run={run_id}] Saltando fase {phase_id} ({label}) - Ya completada")
                continue
            
            current_phase_config = {
                k: v for k, v in {
                    "githubToken": user_config.get("githubToken") if "github" in connectors else None,
                    "notionToken": user_config.get("notionToken") if "notion" in connectors else None,
                    "notionWorkspaceId": user_config.get("notionWorkspaceId") if "notion" in connectors else None
                }.items() if v is not None
            }

            set_user_context(user_id_internal, session_id, current_phase_config)

            # 1. Verificar Presupuesto antes de cada fase (🛑 Bloqueo Activo)
            await session_manager.add_pipeline_log(
                session_id=session_id, type="budget_check",
                message=f"💰 Verificando presupuesto antes de fase {phase_id} ({label})",
                phase_id=phase_id, phase_label=label, level="debug"
            )
            authorized = await BudgetGuardian.check_budget_authorization(user_id_internal)
            logger.debug(f"[run={run_id}] Budget check phase={phase_id} authorized={authorized}")
            if not authorized:
                error_msg = "🚨 EJECUCIÓN SUSPENDIDA: Se ha alcanzado el límite de presupuesto diario."
                await session_manager.update_session(session_id, status="failed", errorMessage=error_msg)
                await session_manager.broadcast_to_session(session_id, {
                    "type": "pipeline_error",
                    "error": error_msg,
                    "code": "BUDGET_EXCEEDED"
                })
                await session_manager.add_pipeline_log(
                    session_id=session_id, type="pipeline_error",
                    message=error_msg, level="error",
                    phase_id=phase_id, phase_label=label,
                    metadata={"code": "BUDGET_EXCEEDED"}
                )
                return

            # 2. Human-in-the-Loop: Puntos de Control y Aprobación
            # Automatizamos que el Agente de Arquitectura siempre pida aprobación antes de seguir
            if agent_role == "architecture_agent":
                logger.info(f"[run={run_id}] Waiting for HITL approval at phase={phase_id} ({label})")
                await session_manager.update_session(session_id, status="awaiting_approval")
                approval_msg = "🏗️ Arquitectura generada. Por favor, revisa y aprueba para continuar con el desarrollo."
                await session_manager.broadcast_to_session(session_id, {
                    "type": "awaiting_approval",
                    "phase": label,
                    "message": approval_msg
                })
                await session_manager.add_pipeline_log(
                    session_id=session_id, type="awaiting_approval",
                    message=approval_msg, phase_id=phase_id, phase_label=label, level="info"
                )

                # Bucle de espera hasta que el estado cambie a "approved" o el proceso se cancele
                wait_cycles = 0
                while True:
                    await asyncio.sleep(2)
                    wait_cycles += 1
                    sess = await session_manager.get_session(session_id)
                    if wait_cycles % 5 == 0:
                        logger.debug(
                            f"[run={run_id}] HITL wait phase={phase_id} poll={wait_cycles} status={getattr(sess, 'status', None)}"
                        )
                    if not sess or sess.status == "failed":
                        logger.warning(f"[run={run_id}] HITL wait aborted phase={phase_id} status={getattr(sess, 'status', None)}")
                        return
                    if sess.status == "approved":
                        await session_manager.update_session(session_id, status="working")
                        await session_manager.add_pipeline_log(
                            session_id=session_id, type="hitl_approved",
                            message="✅ Arquitectura aprobada por el usuario. Continuando con el desarrollo.",
                            phase_id=phase_id, phase_label=label, level="info"
                        )
                        break
                    if sess.status == "working": break

            await session_manager.broadcast_to_session(session_id, {
                "type": "phase_start",
                "phase_id": phase_id,
                "phase_label": label,
                "logs": [header]
            })
            await session_manager.add_pipeline_log(
                session_id=session_id, type="phase_start",
                message=header, phase_id=phase_id, phase_label=label,
                agent_name=label, agent_role=agent_role, level="info"
            )
            await session_manager.add_pipeline_log(
                session_id=session_id, type="agent_log",
                message=f"🧠 {label}: iniciando ejecución con modelo {preferred_model}",
                phase_id=phase_id, phase_label=label,
                agent_name=label, agent_role=agent_role, level="debug"
            )
            
            full_context = "\n\n".join([f"RESULTADO FASE {k+1}:\n{resp}" for k, resp in responses.items()])
            lang_prompt = f"IMPORTANTE: Ejecuta tu tarea y responde ÚNICAMENTE en {language_name}."
            
            if i == 0:
                message = f"{lang_prompt}\n\nOBJETIVO PRINCIPAL DEL PROYECTO:\n{prompt}\n\nFASE ACTUAL: {label}\nINSTRUCCIÓN: Genera los requerimientos iniciales y documéntalos."
            else:
                message = f"{lang_prompt}\n\nCONTEXTO PROYECTO: {prompt}\n\nRESULTADOS PREVIOS:\n{full_context}\n\nFASE ACTUAL: {label}\nINSTRUCCIÓN CRÍTICA: Eres el responsable de {label}. Procede a ejecutar las herramientas necesarias para completar esta fase (ej. crear repo, subir código, documentar, etc.). NO te limites a charlar, ACTÚA."
            if "github" in connectors and phase_id >= 4:
                if locked_repo_full_name:
                    message += (
                        f"\n\nREPOSITORIO OFICIAL DE LA SESIÓN (OBLIGATORIO): {locked_repo_full_name}\n"
                        "Debes usar EXACTAMENTE ese `repo_full_name` en las tools de GitHub. "
                        "No inventes otro owner/repo y no uses placeholders."
                    )
                else:
                    message += (
                        "\n\nAún no hay repositorio oficial detectado. "
                        "Si debes subir archivos, primero confirma o crea repo en la cuenta autenticada y reutiliza ese mismo repo en adelante."
                    )

            start_t = datetime.now()
            phase_agent = await _build_phase_agent(
                agent_role=agent_role,
                user_agents=user_agents,
                preferred_model=preferred_model,
                user_id=user_id_internal,
                session_id=session_id,
            )
            logger.info(
                f"[run={run_id}] Phase agent ready phase={phase_id} agent_name={getattr(phase_agent, 'name', 'unknown')} model={getattr(phase_agent, 'model', preferred_model)}"
            )

            session = await session_service.create_session(app_name="tripkode-agents", user_id=user_id_internal)
            logger.debug(f"[run={run_id}] ADK session created adk_session_id={session.id} phase={phase_id}")
            from core.llm.dispatcher import LLMDispatcher
            from core.security.sanitizer import sanitize_prompt
            preferred_model = getattr(user_db, "preferredModel", "gemini-flash") or "gemini-flash"

            # Sanitizamos también el log local para máxima seguridad en MongoDB
            sanitized_task = sanitize_prompt(message)[:200]
            logger.debug(
                f"[run={run_id}] Prepared prompt phase={phase_id} raw_len={len(message)} sanitized_preview_len={len(sanitized_task)}"
            )

            activity_id = await session_manager.add_agent_activity(
                session_id=session_id,
                agent_name=label,
                agent_role=agent_role,
                task=sanitized_task,
                model=preferred_model
            )
            logger.debug(f"[run={run_id}] Agent activity created phase={phase_id} activity_id={activity_id}")

            # Recibir respuesta con conteo de tokens real
            response_text, in_tok, out_tok = await LLMDispatcher.run_agent(
                agent=phase_agent,
                session_service=session_service,
                user_id=user_id_internal,
                session_id=session.id,
                message=message,
                preferred_model=preferred_model,
                pipeline_session_id=session_id,  # UUID real del pipeline para logs
                phase_id=phase_id,
                phase_label=label,
                agent_role=agent_role,
            )
            response_preview = (response_text or "").strip().replace("\n", " ")[:300]
            await session_manager.add_pipeline_log(
                session_id=session_id, type="agent_log",
                message=f"🧾 {label}: respuesta recibida ({len(response_text or '')} chars)",
                detail=response_preview,
                phase_id=phase_id, phase_label=label,
                agent_name=label, agent_role=agent_role, level="debug"
            )
            logger.info(
                f"[run={run_id}] Agent execution finished phase={phase_id} input_tokens={in_tok} output_tokens={out_tok} response_len={len(response_text or '')}"
            )
            
            # Calcular costo real para esta tarea
            task_cost = calculate_activity_cost(preferred_model, in_tok, out_tok)
            
            responses[i] = response_text
            
            end_t = datetime.now()
            duration = int((end_t - start_t).total_seconds() * 1000)
            
            # Actualizar actividad con métricas REALES
            await session_manager.update_agent_activity(
                activity_id,
                status="completed",
                endTime=end_t,
                durationMs=duration,
                inputTokens=in_tok,
                outputTokens=out_tok,
                tokenCount=in_tok+out_tok,
                costEstimate=task_cost
            )
            logger.debug(
                f"[run={run_id}] Agent activity updated phase={phase_id} duration_ms={duration} task_cost={task_cost:.6f}"
            )

            db_sess_obj = None
            try:
                db_sess_obj = await db_manager.client.projectsession.find_unique(where={"sessionId": session_id})
                if db_sess_obj:
                    # Actualizar sesión con costos acumulados
                    await db_manager.client.projectsession.update(
                        where={"id": db_sess_obj.id},
                        data={
                            "costEstimate": (getattr(db_sess_obj, "costEstimate", 0) or 0) + task_cost,
                            "totalTokens": (getattr(db_sess_obj, "totalTokens", 0) or 0) + (in_tok+out_tok),
                            "inputTokens": (getattr(db_sess_obj, "inputTokens", 0) or 0) + in_tok,
                            "outputTokens": (getattr(db_sess_obj, "outputTokens", 0) or 0) + out_tok,
                            "totalDurationMs": (getattr(db_sess_obj, "totalDurationMs", 0) or 0) + duration
                        }
                    )
            except Exception as hq_err:
                logger.warning(
                    f"[run={run_id}] No se pudo actualizar métricas acumuladas de sesión en DB (phase={phase_id}): {hq_err}",
                    exc_info=True
                )

            try:
                await session_manager.update_session(
                    session_id,
                    totalDurationMs=(getattr(db_sess_obj, "totalDurationMs", 0) or 0) + duration
                )
            except Exception as update_err:
                logger.warning(
                    f"[run={run_id}] Falló update_session(totalDurationMs) phase={phase_id}: {update_err}",
                    exc_info=True
                )

            found_artifacts = await extract_and_link_artifacts(session_id, response_text or "", user_config=user_config)
            if found_artifacts.get("repoUrl"):
                try:
                    locked_repo_full_name = _normalize_repo_full_name(str(found_artifacts["repoUrl"]))
                except Exception:
                    pass
            try:
                curr_for_repo = await session_manager.get_session(session_id)
                repos_now = getattr(curr_for_repo, "githubRepos", []) or []
                if repos_now:
                    last_full_name = _normalize_repo_full_name(getattr(repos_now[-1], "fullName", None))
                    if last_full_name:
                        locked_repo_full_name = last_full_name
            except Exception:
                pass
            logger.info(
                f"[run={run_id}] Artifact extraction finished phase={phase_id} repo={found_artifacts.get('repoUrl')} locked_repo={locked_repo_full_name} notion={found_artifacts.get('notionDoc', {}).get('url') if found_artifacts.get('notionDoc') else None}"
            )
            
            await session_manager.add_message(session_id, "assistant", f"Fase {phase_id} ({label}) completada:\n{response_text}")
            
            await session_manager.broadcast_to_session(session_id, {
                "type": "phase_complete",
                "phase_id": phase_id,
                "phase_label": label,
                "logs": [f"✅ Fase {phase_id} completada", response_text],
                "message": response_text,
                "repoUrl": found_artifacts.get("repoUrl"),
                "notionDoc": found_artifacts.get("notionDoc"),
                "done": True
            })
            await session_manager.add_pipeline_log(
                session_id=session_id, type="phase_complete",
                message=f"✅ Fase {phase_id} ({label}) completada",
                detail=response_text,
                phase_id=phase_id, phase_label=label, agent_role=agent_role,
                metadata={
                    "input_tokens": in_tok, "output_tokens": out_tok,
                    "duration_ms": duration, "cost": task_cost,
                    "repo_url": found_artifacts.get("repoUrl"),
                    "notion_url": found_artifacts.get("notionDoc", {}).get("url") if found_artifacts.get("notionDoc") else None
                },
                level="info"
            )
            
            curr_db_sess = await session_manager.get_session(session_id)
            prev_completed = getattr(curr_db_sess, "completedPhases", [])
            new_completed = list(set(prev_completed + [phase_id]))
            
            await session_manager.update_session(
                session_id,
                currentPhase=phase_id,
                completedPhases=new_completed
            )
            logger.info(
                f"[run={run_id}] Phase committed phase={phase_id} completed_phases={sorted(new_completed)}"
            )
        
        final_result = {"prompt": prompt, "phases_completed": len(phases)}
        await session_manager.update_session(session_id, status="completed", currentPhase=None)
        await session_manager.broadcast_to_session(session_id, {"type": "pipeline_complete", "session_id": session_id, "result": final_result})
        await session_manager.add_pipeline_log(
            session_id=session_id, type="pipeline_complete",
            message=f"🏁 Pipeline completado. {len(phases)} fases ejecutadas.",
            metadata={"phases_completed": len(phases)}, level="info"
        )
        logger.info(f"[run={run_id}] Pipeline completed successfully phases={len(phases)} session={session_id}")
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        tb = traceback.format_exc()
        logger.exception(
            f"[run={run_id}] ❌ Error en pipeline session={session_id} phase={current_phase_id} label={current_phase_label} role={current_phase_role}: {error_msg}"
        )
        await session_manager.update_session(session_id, status="failed", errorMessage=error_msg)
        await session_manager.broadcast_to_session(session_id, {"type": "pipeline_error", "session_id": session_id, "error": error_msg})
        await session_manager.add_pipeline_log(
            session_id=session_id, type="pipeline_error",
            message=f"❌ Error fatal en pipeline: {error_msg}",
            detail=tb,
            phase_id=current_phase_id,
            phase_label=current_phase_label,
            agent_role=current_phase_role,
            metadata={"run_id": run_id},
            level="error"
        )

        if webhook_url:
            logger.info(f"[run={run_id}] Sending error webhook for failed pipeline")
            await session_manager.send_webhook(webhook_url, {"event": "pipeline_complete", "session_id": session_id, "error": error_msg})
