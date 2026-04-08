from contextvars import ContextVar
from typing import Optional, Dict, Any, List
from core.db import db_manager
import logging

logger = logging.getLogger(__name__)

# --- Context Stores ---

# Almacena el contexto de ejecución actual de la factoría
user_context_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar("user_cx", default=None)

def set_user_context(user_id: str, session_id: Optional[str] = None, config: Dict[str, Any] = {}):
    """Establece la identidad y configuración del usuario para el hilo de ejecución actual."""
    return user_context_var.set({
        "user_id": user_id,
        "session_id": session_id,
        "config": config
    })

def get_user_context() -> Optional[Dict[str, Any]]:
    ctx = user_context_var.get()
    if not ctx:
        return None
    # Retornar una copia plana donde config esté mezclada para acceso directo (notionToken, etc)
    merged = ctx.copy()
    if "config" in merged and isinstance(merged["config"], dict):
        config_data = merged.pop("config")
        merged.update(config_data)
    return merged

def get_user_id() -> Optional[str]:
    ctx = user_context_var.get()
    return ctx.get("user_id") if ctx else None

def get_session_id() -> Optional[str]:
    ctx = user_context_var.get()
    return ctx.get("session_id") if ctx else None

def get_user_config() -> Dict[str, Any]:
    ctx = user_context_var.get()
    if ctx and "config" in ctx:
        return ctx["config"]
    return {}

# --- Active Orchestration Logic ---

async def get_augmented_system_prompt(user_id: str, session_id: Optional[str], agent_role_slug: str, base_system_prompt: str) -> str:
    """
    Inyecta dinámicamente las leyes universales de la factoría y las verdades de estado 
    de la sesión en el prompt del agente.
    """
    if not user_id:
        return base_system_prompt

    # 1. Recuperar Contexto Global (Governance)
    global_ctx = await db_manager.client.userglobalcontext.find_unique(where={"userId": user_id})
    
    # 2. Recuperar Decisiones (State of Truth)
    decisions = []
    if session_id:
        decisions = await db_manager.client.sessiondecision.find_many(
            where={
                "session": {"is": {"sessionId": session_id}},
                "status": "active"
            },
            order={"createdAt": "desc"}
        )

    # 3. Construir Bloque de Contexto (V2 High-Performance)
    governance_blocks = []
    
    if global_ctx:
        block = "### LEYES UNIVERSALES DE LA FACTORÍA (USER CONTEXT)\n"
        if global_ctx.techStack:
            block += f"- **Stack Tecnológico**: {', '.join(global_ctx.techStack)}\n"
        if global_ctx.codingStyle:
            block += f"- **Estilo & Patrones**: {global_ctx.codingStyle}\n"
        if global_ctx.constraints:
            block += "- **Restricciones Críticas**:\n  * " + "\n  * ".join(global_ctx.constraints) + "\n"
        governance_blocks.append(block)

    if decisions:
        block = "### ESTADO DE VERDAD DEL PROYECTO (SESSION DECISIONS)\n"
        block += "Estas decisiones han sido validadas previamente y no deben ser ignoradas:\n"
        for d in decisions:
            block += f"- [{d.category.upper()}] {d.decision}"
            if d.rationale: block += f" (Razón: {d.rationale})"
            block += "\n"
        governance_blocks.append(block)

    if not governance_blocks:
        return base_system_prompt

    # 4. Inyección Visual (Primacy Effect)
    header = "\n" + "!"*60 + "\n"
    header += "  SISTEMA DE GOBERNANZA ACTIVO - CUMPLIMIENTO OBLIGATORIO\n"
    header += "!"*60 + "\n\n"
    
    full_governance = header + "\n\n".join(governance_blocks) + "\n" + "!"*60 + "\n\n"
    
    return f"{full_governance}\n\n{base_system_prompt}"

async def log_session_decision(session_id: str, category: str, decision: str, rationale: Optional[str] = None):
    """
    Registra una nueva verdad de estado para la sesión.
    Resuelve automáticamente conflictos marcando decisiones previas de la misma
    categoría como 'superseded' para evitar alucinaciones.
    """
    # 1. Crear la nueva decisión
    new_d = await db_manager.client.sessiondecision.create(
        data={
            "session": {"connect": {"sessionId": session_id}},
            "category": category,
            "decision": decision,
            "rationale": rationale,
            "status": "active"
        }
    )
    
    # 2. Invalidar decisiones anteriores en la misma categoría
    await db_manager.client.sessiondecision.update_many(
        where={
            "session": {"is": {"sessionId": session_id}},
            "category": category,
            "status": "active",
            "id": {"not": new_d.id}
        },
        data={
            "status": "superseded",
            "replacedById": new_d.id
        }
    )
    
    return new_d
