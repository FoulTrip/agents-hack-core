import os
from fastapi import APIRouter, Header, HTTPException, Depends
from services.billing_reconciliation import bill_recon
from core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/recon", tags=["reconciliation"])

# ⚠️ En producción, configurar CLOUD_SCHEDULER_SECRET en .env
RECON_SECRET = os.getenv("CLOUD_SCHEDULER_SECRET", "developer_test_secret")

def verify_scheduler_auth(authorization: str = Header(None)):
    """
    Verifica que la petición venga de un cliente autorizado (p.ej. Google Cloud Scheduler)
    Opcionalmente se puede usar OIDC si está desplegado en Cloud Run, pero aquí usamos un Bearer simple.
    """
    if not authorization or authorization != f"Bearer {RECON_SECRET}":
        logger.warning("🚫 Intento de reconciliación no autorizado.")
        raise HTTPException(status_code=403, detail="No autorizado")
    return True

@router.post("/billing")
async def trigger_billing_reconciliation(authorized: bool = Depends(verify_scheduler_auth)):
    """
    Endpoint activado por Google Cloud Scheduler.
    Sincroniza balances locales con la factualidad del GCP Billing.
    """
    try:
        summary = await bill_recon.reconcile_all_users()
        logger.info(f"📊 Reconciliación exitosa: {summary}")
        return {"status": "success", "summary": summary}
    except Exception as e:
        logger.error(f"🚨 Falla crítica en reconciliación: {e}")
        raise HTTPException(status_code=500, detail=str(e))
