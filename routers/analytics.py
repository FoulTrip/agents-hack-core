from typing import Optional, Any, cast
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from routers.auth import get_current_user
from core.db import db_manager
from core.logger import get_logger
from services.billing_gcp import GCPBillingService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])
billing_gcp = GCPBillingService()

# Google Cloud Vertex AI Pricing (Approximate per 1M tokens)
PRICING_MODELS = {
    "gemini-1.5-pro":   {"input": 1.25, "output": 3.75},   # $1.25 in / $3.75 out
    "gemini-1.5-flash": {"input": 0.075, "output": 0.3},    # $0.075 in / $0.3 out
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},  # $3.00 in / $15.00 out
    "default":          {"input": 0.5, "output": 1.5}
}

def calculate_cost(model_name: str | None, input_tokens: int, output_tokens: int) -> float:
    model_name = (model_name or "default").lower()
    pricing = PRICING_MODELS.get(model_name)
    if not pricing:
        # Trivial attempt to match variants like "gemini-pro" -> "gemini-1.5-pro"
        if "pro" in model_name: pricing = PRICING_MODELS["gemini-1.5-pro"]
        elif "flash" in model_name: pricing = PRICING_MODELS["gemini-1.5-flash"]
        elif "sonnet" in model_name: pricing = PRICING_MODELS["claude-3-5-sonnet"]
        else: pricing = PRICING_MODELS["default"]
    
    cost_in = (input_tokens / 1_000_000) * pricing["input"]
    cost_out = (output_tokens / 1_000_000) * pricing["output"]
    return cost_in + cost_out

class BudgetUpdate(BaseModel):
    dailyLimitUsd: Optional[float] = None
    monthlyLimitUsd: Optional[float] = None
    perAgentLimitUsd: Optional[float] = None
    alertThreshold: Optional[float] = None


@router.get("")
async def get_analytics(start: Optional[str] = None, end: Optional[str] = None, user: dict = Depends(get_current_user)):
    start_dt = datetime.fromisoformat(start) if start else datetime.now() - timedelta(days=30)
    end_dt   = datetime.fromisoformat(end)   if end   else datetime.now()
    
    sessions = await db_manager.client.projectsession.find_many(
        where={"userId": user["id"], "createdAt": {"gte": start_dt, "lte": end_dt}},
        include={"agentActivities": True}
    )
    
    total_cost    = 0.0
    total_tokens  = 0
    input_tokens  = 0
    output_tokens = 0
    
    agent_spend: dict = {}
    model_usage: dict = {} # {model_name: {tokens: 0, cost: 0.0}}

    for s in sessions:
        # Sum main session counters (backwards compatibility)
        total_tokens  += getattr(s, "totalTokens", 0) or 0
        input_tokens  += getattr(s, "inputTokens", 0) or 0
        output_tokens += getattr(s, "outputTokens", 0) or 0
        
        # Calculate per-activity exact cost based on specific model used
        for act in getattr(s, "agentActivities", []):
            i_tok = getattr(act, "inputTokens", 0) or 0
            o_tok = getattr(act, "outputTokens", 0) or 0
            a_model = getattr(act, "model", "gemini-1.5-flash") or "gemini-1.5-flash"
             
            a_cost = calculate_cost(a_model, i_tok, o_tok)
            total_cost += a_cost
            
            # Agent breakdown
            agent_spend[act.agentRole] = agent_spend.get(act.agentRole, 0.0) + a_cost
            
            # Model breakdown
            if a_model not in model_usage:
                model_usage[a_model] = {"tokens": 0, "cost": 0.0}
            model_usage[a_model]["tokens"] += (i_tok + o_tok)
            model_usage[a_model]["cost"] += a_cost

    total_runs    = len(sessions)
    success_runs  = sum(1 for s in sessions if s.status == "completed")
    durations     = [getattr(s, "totalDurationMs", 0) or 0 for s in sessions]
    avg_runtime   = int(sum(durations) / len(durations)) if durations else 0
    
    return {
        "dateRange": {"start": start_dt.isoformat(), "end": end_dt.isoformat()},
        "spend": {
            "total": round(total_cost, 6), 
            "currency": "USD",
            "perUserAverage": round(total_cost / (len(sessions) or 1), 6)
        },
        "usage": {"totalTokens": total_tokens, "inputTokens": input_tokens, "outputTokens": output_tokens},
        "performance": {
            "totalRuns": total_runs, 
            "successRuns": success_runs, 
            "successRate": round(success_runs / total_runs, 2) if total_runs else None, 
            "avgRuntimeMs": avg_runtime
        },
        "agentSpend": agent_spend,
        "modelBreakdown": model_usage
    }


@router.get("/gcloud")
async def get_gcloud_metrics(days: int = 30, user: dict = Depends(get_current_user)):
    """
    Usa el SDK oficial de GCloud Monitoring para ver los tokens consumidos
    por este usuario (gracias a los LABELS inyectados).
    """
    usage = await billing_gcp.get_usage_by_user(user["id"], days=days)
    
    total_tokens = sum(usage.values())
    # Estimar USD basado en tokens reales de la API de GCP
    estimated_usd = total_tokens * (0.00001875 / 1000) # Promedio Flash/Pro
    
    return {
        "status": "success",
        "source": "Google Cloud Monitoring SDK",
        "userId": user["id"],
        "periodDays": days,
        "metrics": usage,
        "totalTokens": total_tokens,
        "estimatedUsd": round(estimated_usd, 6)
    }


@router.get("/budget")
async def get_budget(user: dict = Depends(get_current_user)):
    budget = await db_manager.client.analyticsbudget.find_first(where={"userId": user["id"]})
    if not budget:
        return {"dailyLimitUsd": None, "monthlyLimitUsd": None, "perAgentLimitUsd": None, "alertThreshold": 0.8}
    return {"dailyLimitUsd": getattr(budget, "dailyLimitUsd", None), "monthlyLimitUsd": getattr(budget, "monthlyLimitUsd", None), "perAgentLimitUsd": getattr(budget, "perAgentLimitUsd", None), "alertThreshold": getattr(budget, "alertThreshold", 0.8)}


@router.patch("/budget")
async def update_budget(body: BudgetUpdate, user: dict = Depends(get_current_user)):
    data = cast(Any, body.dict(exclude_unset=True))
    existing = await db_manager.client.analyticsbudget.find_first(where={"userId": user["id"]})
    if existing:
        await db_manager.client.analyticsbudget.update(where={"id": existing.id}, data=data)
    else:
        await db_manager.client.analyticsbudget.create(data=cast(Any, {"userId": user["id"], **data}))
    return {"status": "success"}