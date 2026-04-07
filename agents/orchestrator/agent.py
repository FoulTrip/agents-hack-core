from google.adk.agents import Agent
from core.config import settings
from core.logger import get_logger
from .prompts import SYSTEM_PROMPT
from .tools import propose_project_decision
from agents.requirements.agent import create_requirements_agent
from agents.architecture.agent import create_architecture_agent
from agents.development.agent import create_development_agent
from agents.qa.agent import create_qa_agent
from agents.documentation.agent import create_documentation_agent
from agents.devops.agent import create_devops_agent

logger = get_logger(__name__)

async def create_orchestrator(
    user_agents: list | None = None, 
    model: str = "gemini-3-flash-preview",
    user_id: str | None = None,
    session_id: str | None = None
) -> Agent:
    """
    Crea el agente orquestador con soporte para inyección dinámica de gobernanza (Punto 1).
    """
    logger.debug(f"Creando Orchestrator Agent con el modelo: {model} para usuario {user_id}")
    user_agents = user_agents or []
    
    from core.context import get_augmented_system_prompt
    
    # Aumentar el prompt del orquestador con gobernanza global y decisiones de sesión
    final_instruction = SYSTEM_PROMPT
    if user_id:
        final_instruction = await get_augmented_system_prompt(
            user_id, session_id, "orchestrator", SYSTEM_PROMPT
        )
    
    return Agent(
        name="orchestrator",
        model=model,
        description="Agente principal que coordina todo el sistema de desarrollo",
        instruction=final_instruction,
        sub_agents=[
            await create_requirements_agent(user_agents, model=model, user_id=user_id, session_id=session_id),
            await create_architecture_agent(user_agents, model=model, user_id=user_id, session_id=session_id),
            await create_development_agent(user_agents, model=model, user_id=user_id, session_id=session_id),
            await create_qa_agent(user_agents, model=model, user_id=user_id, session_id=session_id),
            await create_documentation_agent(user_agents, model=model, user_id=user_id, session_id=session_id),
            await create_devops_agent(user_agents, model=model, user_id=user_id, session_id=session_id),
        ],
        tools=[propose_project_decision],
    )