from google.adk.agents import Agent
from core.logger import get_logger
from .prompts import SYSTEM_PROMPT
from .tools import setup_repository_tool, create_file_tool, create_multiple_files_tool

logger = get_logger(__name__)

async def create_development_agent(
    user_agents: list = None, 
    model: str = "gemini-3-flash-preview",
    user_id: str | None = None,
    session_id: str | None = None
) -> Agent:
    """
    Crea el agente de desarrollo con inyección dinámica de gobernanza y decisiones.
    """
    logger.debug(f"Creando Development Agent con modelo: {model} para usuario {user_id}")
    user_agents = user_agents or []
    
    my_config = next((a for a in user_agents if getattr(a, "role", "") == "development_agent"), None)
    agent_model = getattr(my_config, "model", model) if my_config else model
    instruction = SYSTEM_PROMPT
    
    from core.context import get_augmented_system_prompt
    
    if my_config:
        custom_parts = []
        if getattr(my_config, "personality", None):
            custom_parts.append(f"Tu personalidad: {my_config.personality}")
        if getattr(my_config, "context", None):
            custom_parts.append(f"Tu contexto: {my_config.context}")
        if getattr(my_config, "guidelines", None):
            custom_parts.append(f"Reglas y directrices extra: {my_config.guidelines}")
        
        if custom_parts:
            instruction += "\n\n<<<CONFIGURACIÓN PERSONALIZADA DEL USUARIO>>>\n" + "\n".join(custom_parts)

    # Aumentar con Gobernanza y Decisiones (Context V2)
    if user_id:
        instruction = await get_augmented_system_prompt(
            user_id, session_id, "development_agent", instruction
        )
    
    return Agent(
        name="development_agent",
        model=agent_model,
        description="Genera el código fuente base del proyecto y lo sube a un repositorio de GitHub.",
        instruction=instruction,
        tools=[setup_repository_tool, create_file_tool, create_multiple_files_tool],
    )