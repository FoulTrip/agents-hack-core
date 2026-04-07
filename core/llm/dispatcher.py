import os
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from core.security.sanitizer import sanitize_prompt
from .setup import setup_adk_vertex

# Ejecutar configuración de Vertex AI al importar
setup_adk_vertex()

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
            agent.model = preferred_model
            
        config = types.GenerateContentConfig(
            labels={
                "user_id": str(user_id).replace("-", "_"),
                "session_id": str(session_id).replace("-", "_")
            }
        )

        runner = Runner(agent=agent, app_name="software-factory", session_service=session_service)
        
        response_text = ""
        input_tokens = 0
        output_tokens = 0

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=sanitized_message)]),
            config=config 
        ):
            # Capturar metadatos del uso si están disponibles en el evento
            if hasattr(event, "response") and event.response and hasattr(event.response, "usage_metadata") and event.response.usage_metadata:
                usage = event.response.usage_metadata
                input_tokens = getattr(usage, "prompt_token_count", input_tokens)
                output_tokens = getattr(usage, "candidates_token_count", output_tokens)

            if event.is_final_response() and event.content and event.content.parts:
                response_text = event.content.parts[0].text
        
        return response_text, input_tokens, output_tokens
