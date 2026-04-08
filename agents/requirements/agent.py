from google.adk.agents import Agent
from core.logger import get_logger
from .prompts import SYSTEM_PROMPT
from .tools import save_requirements_tool

logger = get_logger(__name__)

async def create_requirements_agent(
    user_agents: list = None, 
    model: str = "gemini-3-flash-preview",
    user_id: str | None = None,
    session_id: str | None = None
) -> Agent:
    """
    Crea el agente de requerimientos con prompts aumentados dinámicamente.
    """
    logger.debug(f"Creando Requirements Agent con modelo: {model}")
    user_agents = user_agents or []
    
    from core.llm.dispatcher import MODEL_ALIASES
    from core.context import get_augmented_system_prompt
    from core.personality import get_personality_instruction
    
    my_config = next((a for a in user_agents if getattr(a, "role", "") == "requirements_agent"), None)

    # Parámetros individuales del agente
    agent_model = model
    agent_temp = 0.7
    agent_max_tokens = 4096

    if my_config:
        if getattr(my_config, "model", None):
            agent_model = MODEL_ALIASES.get(my_config.model, my_config.model)
        
        agent_temp = getattr(my_config, "temperature", 0.7)
        agent_max_tokens = getattr(my_config, "maxTokens", 4096)

    instruction = SYSTEM_PROMPT
    
    if my_config:
        custom_parts = []
        if getattr(my_config, "context", None):
            custom_parts.append(f"Tu contexto: {my_config.context}")
        if getattr(my_config, "guidelines", None):
            custom_parts.append(f"Reglas y directrices extra: {my_config.guidelines}")
        
        # Inyectar modulación matemática de los 5 rasgos (Big Five)
        personality_text = get_personality_instruction(my_config)
        
        if custom_parts or personality_text:
            instruction += "\n\n<<<CONFIGURACIÓN PERSONALIZADA DEL USUARIO>>>\n" + "\n".join(custom_parts) + personality_text

    # Aumentar con Gobernanza y Decisiones
    if user_id:
        instruction = await get_augmented_system_prompt(
            user_id, session_id, "requirements_agent", instruction
        )
    
    return Agent(
        name="requirements_agent",
        model=agent_model,
        description="Analiza solicitudes de software y genera documentos de requerimientos detallados. Guarda el resultado en Notion.",
        instruction=instruction,
        tools=[save_requirements_tool],
        generate_content_config={
            "temperature": agent_temp,
            "max_output_tokens": agent_max_tokens,
        },
    )