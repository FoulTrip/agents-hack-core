from google.adk.tools import tool

@tool
def propose_project_decision(category: str, decision: str, rationale: str) -> str:
    """
    IMPORTANTE: Úsala SOLAMENTE cuando notes que el usuario y tú (u otros agentes)
    hayan acordado un nuevo estándar técnico, cambio de arquitectura, o regla de oro
    para el proyecto actual.
    
    Args:
        category: "architecture", "ui_ux", "business_logic", "tech_stack", "security".
        decision: La regla o decisión exacta acordada (Ej: "Usar MongoDB en lugar de PostgreSQL").
        rationale: Razón breve de por qué se acordó esto.
    """
    from core.context import log_session_decision, get_session_id
    from core.logger import get_logger
    import asyncio
    
    logger = get_logger(__name__)
    session_id = get_session_id()
    
    if not session_id:
        return "ADVERTENCIA: No hay una sesión activa para registrar la decisión."
    
    # Dado que `log_session_decision` es async, y esta tool puede ser síncrona en el runner:
    # Usamos asyncio.run o creamos una task si ya estamos en un event loop.
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(log_session_decision(session_id, category, decision, rationale))
    except RuntimeError:
        asyncio.run(log_session_decision(session_id, category, decision, rationale))
        
    logger.info(f"🧠 Aprendizaje Dinámico - Decisión registrada: {decision}")
    
    return f"¡Hecho! He registrado oficialmente la decisión: '{decision}' como parte del Estado de Verdad del proyecto."
