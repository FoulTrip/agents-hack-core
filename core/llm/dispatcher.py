import os
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from core.security.sanitizer import sanitize_prompt
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

        # 🛡️ Sanitización de Datos (PII Redaction)
        sanitized_message = sanitize_prompt(message)
        if preferred_model:
            agent.model = MODEL_ALIASES.get(preferred_model, preferred_model)

        # 🔥 RUTEO DINÁMICO MULTI-ENTORNO
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

        response_text = ""
        input_tokens = 0
        output_tokens = 0

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=sanitized_message)])
        ):
            # ── 1. Log de texto del agente (pensamiento, razonamiento) ──────────
            if hasattr(event, "log") and event.log:
                log_msg = f"🤖 {event.log}"
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
                    tool_name = getattr(tc, "name", str(tc))
                    tool_args = getattr(tc, "args", {})
                    log_msg = f"🔧 Tool call: {tool_name}"
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
                    tool_name = getattr(tr, "name", str(tr))
                    tool_output_obj = getattr(tr, "output", {})
                    tool_output = str(tool_output_obj)
                    log_msg = f"✅ Tool result: {tool_name}"
                    
                    # 🔍 Extraer Artifacts (Notion Fallback)
                    if isinstance(tool_output_obj, dict) and "markdown" in tool_output_obj:
                        await sm.add_artifact(
                            session_id=log_session_id,
                            type="notion_doc",
                            title=f"Backup: {tool_name}",
                            url=tool_output_obj.get("url"),
                            content=tool_output_obj.get("markdown")
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

        return response_text, input_tokens, output_tokens
