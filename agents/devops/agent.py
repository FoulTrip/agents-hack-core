from google.adk.agents import Agent
from core.logger import get_logger
from .prompts import SYSTEM_PROMPT
from .tools import setup_devops_tool

logger = get_logger(__name__)

async def create_devops_agent(
    user_agents: list = None, 
    model: str = "gemini-3-flash-preview",
    user_id: str | None = None,
    session_id: str | None = None
) -> Agent:
    """
    Crea el agente DevOps con inyección dinámica de gobernanza y conectores.
    """
    logger.debug(f"Creando DevOps Agent con modelo: {model}")
    user_agents = user_agents or []
    
    from core.llm.dispatcher import MODEL_ALIASES
    from core.context import get_augmented_system_prompt
    
    my_config = next((a for a in user_agents if getattr(a, "role", "") == "devops_agent"), None)

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
        if getattr(my_config, "personality", None):
            custom_parts.append(f"Tu personalidad: {my_config.personality}")
        if getattr(my_config, "context", None):
            custom_parts.append(f"Tu contexto: {my_config.context}")
        if getattr(my_config, "guidelines", None):
            custom_parts.append(f"Reglas y directrices extra: {my_config.guidelines}")
        
        # Inyectar conectores disponibles
        connectors = getattr(my_config, "connectors", [])
        if connectors:
            custom_parts.append(f"CONECTORES DE DESPLIEGUE DISPONIBLES: {', '.join(connectors)}")
            custom_parts.append("Debes priorizar el uso de estos servicios para tus scripts de infraestructura.")
        else:
            custom_parts.append("CONECTORES: No hay conectores de nube específicos. Usa Docker Genérico.")
        
        if custom_parts:
            instruction += "\n\n<<<CONFIGURACIÓN PERSONALIZADA DEL USUARIO>>>\n" + "\n".join(custom_parts)

    # Aumentar con Gobernanza y Decisiones (Context V2)
    if user_id:
        instruction = await get_augmented_system_prompt(
            user_id, session_id, "devops_agent", instruction
        )
    
    return Agent(
        name="devops_agent",
        model=agent_model,
        description="Genera la infraestructura completa de CI/CD, Docker y despliegue del proyecto.",
        instruction=instruction,
        tools=[setup_devops_tool],
        generate_content_config={
            "temperature": agent_temp,
            "max_output_tokens": agent_max_tokens,
        },
    )