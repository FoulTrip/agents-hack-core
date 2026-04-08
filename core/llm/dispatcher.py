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
    async def run_agent(agent, session_service, user_id, session_id, message, preferred_model="gemini-3-flash-preview"):
        """
        Ruta la ejecución de un agente a través de Google ADK.
        Aplica limpieza de PII antes de enviar el prompt.
        Retorna (texto_final, input_tokens, output_tokens)
        """
        
        # 🛡️ Sanitización de Datos (PII Redaction)
        sanitized_message = sanitize_prompt(message)
        if preferred_model:
            agent.model = MODEL_ALIASES.get(preferred_model, preferred_model)
            
        # 🔥 RUTEO DINÁMICO MULTI-ENTORNO 🔥
        # Si el usuario quiere usar Claude, habilitamos temporalmente Vertex AI.
        # Si quiere usar Gemini (incluyendo los nuevos 3.0), apagamos Vertex para que rutee a AI Studio,
        # donde estos modelos existen y resolvemos los errores 404.
        if "claude" in agent.model.lower():
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        else:
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
            
        # Inyectar labels para auditoría / billing directamente en el agente
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

        from models.SessionManager import SessionManager
        sm = SessionManager()

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=sanitized_message)])
        ):
            # 🎙️ Streaming de Logs en Tiempo Real para el Frontend
            if hasattr(event, "log") and event.log:
                # El event.log contiene información del agente (pensamiento, uso de herramientas, etc)
                await sm.broadcast_to_session(session_id, {
                    "type": "agent_log",
                    "logs": [f"🤖 {event.log}"]
                })

            # Capturar metadatos del uso si están disponibles en el evento
            if hasattr(event, "response") and event.response and hasattr(event.response, "usage_metadata") and event.response.usage_metadata:
                usage = event.response.usage_metadata
                input_tokens = getattr(usage, "prompt_token_count", input_tokens)
                output_tokens = getattr(usage, "candidates_token_count", output_tokens)

            if event.is_final_response() and event.content and event.content.parts:
                response_text = event.content.parts[0].text
        
        return response_text, input_tokens, output_tokens
