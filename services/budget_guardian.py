from datetime import datetime, time
from core.db import db_manager
from core.logger import get_logger
from typing import Optional

logger = get_logger(__name__)

# Vertex AI Model Pricing (per 1k tokens)
PRICING = {
    "gemini-1.5-pro":   {"input": 0.00125, "output": 0.00375},
    "gemini-1.5-flash": {"input": 0.00001875, "output": 0.00005625},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    "default":          {"input": 0.0005, "output": 0.0015}
}

def calculate_activity_cost(model: str | None, input_tokens: int, output_tokens: int) -> float:
    model = (model or "default").lower()
    pricing = PRICING.get(model)
    if not pricing:
        if "pro" in model: pricing = PRICING["gemini-1.5-pro"]
        elif "flash" in model: pricing = PRICING["gemini-1.5-flash"]
        elif "sonnet" in model: pricing = PRICING["claude-3-5-sonnet"]
        else: pricing = PRICING["default"]
    
    return (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]

class BudgetGuardian:
    """
    Protege la factoría bloqueando ejecuciones que superen el presupuesto.
    """

    @staticmethod
    async def check_budget_authorization(user_id: str) -> bool:
        """
        Verifica si el usuario tiene presupuesto disponible para el día de hoy.
        """
        # 1. Obtener presupuesto configurado
        budget = await db_manager.client.analyticsbudget.find_first(
            where={"userId": user_id}
        )
        
        if not budget or budget.dailyLimitUsd is None:
            return True # Sin límite configurado
            
        # 2. Calcular gasto de hoy
        today_start = datetime.combine(datetime.now().date(), time.min)
        
        # Obtenemos sesiones de hoy para este usuario
        sessions = await db_manager.client.projectsession.find_many(
            where={
                "userId": user_id,
                "createdAt": {"gte": today_start}
            },
            include={"agentActivities": True}
        )
        
        total_spent_today = 0.0
        for s in sessions:
            for act in s.agentActivities:
                if act.costEstimate:
                    total_spent_today += act.costEstimate
        
        logger.info(f"💰 Presupuesto Diario: ${budget.dailyLimitUsd} | Gastado hoy: ${total_spent_today:.4f}")
        
        if total_spent_today >= budget.dailyLimitUsd:
            logger.warning(f"🚨 BLOQUEO DE PRESUPUESTO para usuario {user_id}. Límite: ${budget.dailyLimitUsd}")
            return False
            
        return True
