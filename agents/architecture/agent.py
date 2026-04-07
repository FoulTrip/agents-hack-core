from google.adk.agents import Agent
from core.logger import get_logger
from .prompts import SYSTEM_PROMPT
from .tools import save_architecture_tool

logger = get_logger(__name__)

async def create_architecture_agent(
    user_agents: list | None = None, 
    model: str = "gemini-3-flash-preview",
    user_id: str | None = None,
    session_id: str | None = None
) -> Agent:
    """
    Crea el agente de arquitectura técnica con prompts aumentados dinámicamente.
    """
    logger.debug(f"Creando Architecture Agent con el modelo: {model} para usuario {user_id}")
    user_agents = user_agents or []
    
    my_config = next((a for a in user_agents if getattr(a, "role", "") == "architecture_agent"), None)
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
            user_id, session_id, "architecture_agent", instruction
        )
    
    return Agent(
        name="architecture_agent",
        model=agent_model,
        description="Diseña la arquitectura técnica completa de un proyecto basándose en los requerimientos. Guarda el resultado en Notion.",
        instruction=instruction,
        tools=[save_architecture_tool],
    )