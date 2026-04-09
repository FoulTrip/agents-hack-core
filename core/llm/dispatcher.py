import os
import re
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from core.security.sanitizer import sanitize_prompt
from core.logger import get_logger
from .setup import setup_adk_vertex

# Ejecutar configuración de Vertex AI al importar
setup_adk_vertex()

# Aliases de modelos para Google AI Studio (Gemini API key)
MODEL_ALIASES = {
    "gemini-flash":       "gemini-3-flash-preview",
    "gemini-pro":         "gemini-3.1-pro-preview",
    "gemini-2.0-flash-001":  "gemini-2.0-flash",
    "gemini-2.0-flash-exp":  "gemini-2.0-flash",
    "gemini-3-flash-preview":  "gemini-2.5-flash",
    "gemini-3.1-pro-preview":    "gemini-2.5-pro",
    "claude":             "claude-sonnet-4-6",
    "claude-sonnet":      "claude-sonnet-4-6",
    "claude-3-5-sonnet":  "claude-sonnet-4-6",
}

logger = get_logger(__name__)

class LLMDispatcher:
    """
    Despachador central con Auditoría y Sanitización de PII.
    """
    @staticmethod
    async def run_agent(
        agent, session_service, user_id, session_id, message,
        preferred_model="gemini-3-flash-preview",
        pipeline_session_id: str | None = None,  # UUID de la sesión del pipeline para logs
        phase_id: int | None = None,
        phase_label: str | None = None,
        agent_role: str | None = None,
    ):
        """
        Ruta la ejecución de un agente a través de Google ADK.
        Aplica limpieza de PII antes de enviar el prompt.
        Persiste todos los eventos del ADK en MongoDB (PipelineLog).
        Retorna (texto_final, input_tokens, output_tokens)
        """
        from models.SessionManager import SessionManager
        sm = SessionManager()

        # El session_id para logs es el UUID de la sesión del pipeline, no el del ADK
        log_session_id = pipeline_session_id or session_id

        # Sanitización de Datos (PII Redaction)
        sanitized_message = sanitize_prompt(message)
        if preferred_model:
            agent.model = MODEL_ALIASES.get(preferred_model, preferred_model)

        # RUTEO DINÁMICO MULTI-ENTORNO
        if "claude" in agent.model.lower():
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        else:
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"

        # Inyectar labels para auditoría / billing
        labels_dict = {
            "user_id": str(user_id).replace("-", "_"),
            "session_id": str(session_id).replace("-", "_")
        }
        if getattr(agent, "generate_content_config", None):
            if hasattr(agent.generate_content_config, "labels"):
                agent.generate_content_config.labels = labels_dict
            elif isinstance(agent.generate_content_config, dict):
                agent.generate_content_config["labels"] = labels_dict
        else:
            agent.generate_content_config = types.GenerateContentConfig(labels=labels_dict)

        runner = Runner(agent=agent, app_name="tripkode-agents", session_service=session_service)
        logger.info(
            f"[dispatcher] start pipeline_session={log_session_id} adk_session={session_id} phase={phase_id} role={agent_role} agent={getattr(agent, 'name', 'unknown')} model={getattr(agent, 'model', preferred_model)}"
        )
        logger.debug(
            f"[dispatcher] prompt sizes pipeline_session={log_session_id} raw_len={len(message or '')} sanitized_len={len(sanitized_message or '')}"
        )

        response_text = ""
        input_tokens = 0
        output_tokens = 0
        linked_repos: set[str] = set()
        linked_notion_pages: set[str] = set()
        event_count = 0
        log_count = 0
        tool_call_count = 0
        tool_result_count = 0

        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part(text=sanitized_message)])
            ):
                event_count += 1
            # ── 1. Log de texto del agente (pensamiento, razonamiento) ──────────
                if hasattr(event, "log") and event.log:
                    log_count += 1
                    log_msg = f"[Agent] {event.log}"
                    await sm.broadcast_to_session(log_session_id, {
                        "type": "agent_log",
                        "logs": [log_msg],
                        "phase_id": phase_id,
                        "phase_label": phase_label,
                    })
                    await sm.add_pipeline_log(
                        session_id=log_session_id,
                        type="agent_log",
                        message=log_msg,
                        phase_id=phase_id,
                        phase_label=phase_label,
                        agent_name=getattr(agent, "name", None),
                        agent_role=agent_role,
                        level="debug",
                    )

            # ── 2. Tool call (el agente invoca una herramienta) ──────────────────
                if hasattr(event, "tool_calls") and event.tool_calls:
                    for tc in event.tool_calls:
                        tool_call_count += 1
                        tool_name = getattr(tc, "name", str(tc))
                        tool_args = getattr(tc, "args", {})
                        log_msg = f"Tool call: {tool_name}"
                        logger.info(
                            f"[dispatcher] tool_call pipeline_session={log_session_id} phase={phase_id} tool={tool_name} args_keys={list(tool_args.keys()) if isinstance(tool_args, dict) else 'n/a'}"
                        )
                        await sm.broadcast_to_session(log_session_id, {
                            "type": "agent_tool_call",
                            "logs": [log_msg],
                            "phase_id": phase_id,
                            "phase_label": phase_label,
                            "tool": tool_name,
                        })
                        await sm.add_pipeline_log(
                            session_id=log_session_id,
                            type="agent_tool_call",
                            message=log_msg,
                            phase_id=phase_id,
                            phase_label=phase_label,
                            agent_name=getattr(agent, "name", None),
                            agent_role=agent_role,
                            metadata={"tool": tool_name, "args": str(tool_args)[:500]},
                            level="info",
                        )

            # ── 3. Tool result (respuesta de la herramienta al agente) ───────────
                if hasattr(event, "tool_results") and event.tool_results:
                    for tr in event.tool_results:
                        tool_result_count += 1
                        tool_name = getattr(tr, "name", str(tr))
                        tool_output_obj = getattr(tr, "output", {})
                        tool_output = str(tool_output_obj)
                        output_preview = tool_output.replace("\n", " ")[:160]
                        log_msg = f"Tool result: {tool_name}" + (f" — {output_preview}" if output_preview else "")
                        logger.info(
                            f"[dispatcher] tool_result pipeline_session={log_session_id} phase={phase_id} tool={tool_name} output_type={type(tool_output_obj).__name__} output_len={len(tool_output)}"
                        )
                    
                    # Extraer Artifacts / Links estructurados desde resultados de tools
                        if isinstance(tool_output_obj, dict):
                        # 1) Enlace de GitHub si la tool devuelve repo_full_name/repo_url
                            repo_full_name = (
                                tool_output_obj.get("effective_repo_full_name")
                                or tool_output_obj.get("repo_full_name")
                                or tool_output_obj.get("full_name")
                            )
                            repo_url = (
                                tool_output_obj.get("effective_repo_url")
                                or tool_output_obj.get("repo_url")
                                or tool_output_obj.get("url")
                            )
                            if not repo_url and isinstance(repo_full_name, str) and "/" in repo_full_name:
                                repo_url = f"https://github.com/{repo_full_name}"

                            if isinstance(repo_full_name, str) and isinstance(repo_url, str) and repo_full_name not in linked_repos:
                                try:
                                    await sm.link_github_repo(
                                        session_id=log_session_id,
                                        name=repo_full_name.split("/")[-1],
                                        url=repo_url,
                                        full_name=repo_full_name,
                                    )
                                    linked_repos.add(repo_full_name)
                                    logger.debug(
                                        f"[dispatcher] linked github repo from tool_result pipeline_session={log_session_id} repo={repo_full_name}"
                                    )
                                except Exception as link_repo_err:
                                    logger.warning(
                                        f"[dispatcher] failed linking github repo pipeline_session={log_session_id} repo={repo_full_name}: {link_repo_err}",
                                        exc_info=True
                                    )

                        # 1.1) Workspace local si la tool devuelve local_project_path
                            local_project_path = tool_output_obj.get("local_project_path")
                            local_written = tool_output_obj.get("local_files_written")
                            if isinstance(local_project_path, str) and local_project_path.strip():
                                try:
                                    await sm.add_artifact(
                                        session_id=log_session_id,
                                        type="local_project",
                                        title=f"Workspace local ({tool_name})",
                                        url=local_project_path,
                                        content=f"files_written={local_written}" if local_written is not None else None,
                                    )
                                    logger.debug(
                                        f"[dispatcher] local workspace artifact saved pipeline_session={log_session_id} path={local_project_path}"
                                    )
                                except Exception as local_art_err:
                                    logger.warning(
                                        f"[dispatcher] failed saving local workspace artifact pipeline_session={log_session_id} path={local_project_path}: {local_art_err}",
                                        exc_info=True
                                    )

                        # 2) Enlace/backup de Notion desde salida directa o anidada.
                            notion_data = tool_output_obj.get("notion") if isinstance(tool_output_obj.get("notion"), dict) else tool_output_obj
                            if isinstance(notion_data, dict):
                                notion_url = notion_data.get("url")
                                notion_page_id = notion_data.get("page_id") or notion_data.get("pageId")
                                notion_markdown = notion_data.get("markdown")
                                notion_title = notion_data.get("title") or f"Documento: {tool_name}"

                                if isinstance(notion_page_id, str) and notion_page_id and notion_page_id not in linked_notion_pages:
                                    try:
                                        resolved_notion_url = str(notion_url) if notion_url else f"https://www.notion.so/{notion_page_id.replace('-', '')}"
                                        await sm.link_notion_page(
                                            session_id=log_session_id,
                                            title=str(notion_title),
                                            url=resolved_notion_url,
                                            page_id=notion_page_id,
                                            content=notion_markdown,
                                        )
                                        linked_notion_pages.add(notion_page_id)
                                        logger.debug(
                                            f"[dispatcher] linked notion page from tool_result pipeline_session={log_session_id} page_id={notion_page_id}"
                                        )
                                    except Exception as link_notion_err:
                                        logger.warning(
                                            f"[dispatcher] failed linking notion page pipeline_session={log_session_id} page_id={notion_page_id}: {link_notion_err}",
                                            exc_info=True
                                        )
                                elif isinstance(notion_markdown, str) and notion_markdown:
                                    await sm.add_artifact(
                                        session_id=log_session_id,
                                        type="notion_doc",
                                        title=f"Backup: {tool_name}",
                                        url=notion_url,
                                        content=notion_markdown
                                    )
                                    logger.debug(
                                        f"[dispatcher] notion markdown backup saved pipeline_session={log_session_id} tool={tool_name} markdown_len={len(notion_markdown)}"
                                    )
                        else:
                        # Fallback: si la tool responde solo texto con URL de GitHub/Notion.
                            gh_match = re.search(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", tool_output)
                            if gh_match:
                                repo_full_name = gh_match.group(1)
                                if repo_full_name not in linked_repos:
                                    try:
                                        await sm.link_github_repo(
                                            session_id=log_session_id,
                                            name=repo_full_name.split("/")[-1],
                                            url=f"https://github.com/{repo_full_name}",
                                            full_name=repo_full_name,
                                        )
                                        linked_repos.add(repo_full_name)
                                        logger.debug(
                                            f"[dispatcher] linked github repo from text fallback pipeline_session={log_session_id} repo={repo_full_name}"
                                        )
                                    except Exception as fallback_repo_err:
                                        logger.warning(
                                            f"[dispatcher] failed fallback github link pipeline_session={log_session_id} repo={repo_full_name}: {fallback_repo_err}",
                                            exc_info=True
                                        )

                        await sm.broadcast_to_session(log_session_id, {
                            "type": "agent_tool_result",
                            "logs": [log_msg],
                            "phase_id": phase_id,
                            "phase_label": phase_label,
                            "tool": tool_name,
                            "output_preview": tool_output[:200],
                            "artifact": tool_output_obj if isinstance(tool_output_obj, dict) and "markdown" in tool_output_obj else None
                        })
                        await sm.add_pipeline_log(
                            session_id=log_session_id,
                            type="agent_tool_result",
                            message=log_msg,
                            detail=tool_output,
                            phase_id=phase_id,
                            phase_label=phase_label,
                            agent_name=getattr(agent, "name", None),
                            agent_role=agent_role,
                            metadata={"tool": tool_name},
                            level="info",
                        )

            # ── 4. Capturar métricas de tokens ──────────────────────────────────
                if hasattr(event, "response") and event.response and hasattr(event.response, "usage_metadata") and event.response.usage_metadata:
                    usage = event.response.usage_metadata
                    input_tokens = getattr(usage, "prompt_token_count", input_tokens)
                    output_tokens = getattr(usage, "candidates_token_count", output_tokens)
                    logger.debug(
                        f"[dispatcher] usage update pipeline_session={log_session_id} phase={phase_id} in={input_tokens} out={output_tokens}"
                    )

            # ── 5. Respuesta final ───────────────────────────────────────────────
                if event.is_final_response() and event.content and event.content.parts:
                    full_text = []
                    for part in event.content.parts:
                        if part.text:
                            full_text.append(part.text)
                    if full_text:
                        response_text = "\n".join(full_text)
                    elif not response_text:
                        # Si no hay texto en la respuesta final pero hubo log o herramientas, 
                        # tratamos de dar un feedback mínimo
                        response_text = "Acción completada con éxito por el agente."
        except Exception as run_err:
            logger.exception(
                f"[dispatcher] execution error pipeline_session={log_session_id} adk_session={session_id} phase={phase_id} role={agent_role}: {run_err}"
            )
            raise

        logger.info(
            f"[dispatcher] done pipeline_session={log_session_id} phase={phase_id} events={event_count} logs={log_count} tool_calls={tool_call_count} tool_results={tool_result_count} linked_repos={len(linked_repos)} linked_notion={len(linked_notion_pages)} in_tok={input_tokens} out_tok={output_tokens} response_len={len(response_text or '')}"
        )

        return response_text, input_tokens, output_tokens
