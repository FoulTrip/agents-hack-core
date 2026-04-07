import logging
from datetime import datetime, timedelta, time
from core.db import db_manager
from services.billing_gcp import GCPBillingService

logger = logging.getLogger(__name__)

class BillingReconciliation:
    """
    Servicio de Reconciliación de Facturación.
    Cruza los datos locales con GCloud Monitoring para asegurar precisión contable.
    Pensado para ser invocado externamente por Google Cloud Scheduler.
    """
    
    def __init__(self):
        self.gcp_billing = GCPBillingService()

    async def reconcile_all_users(self):
        """
        Ejecuta la reconciliación para todos los usuarios activos.
        Retorna un resumen de las acciones tomadas.
        """
        logger.info("🕒 Iniciando Reconciliación de Facturación vía Cloud Scheduler...")
        
        summary = {
            "processed_users": 0,
            "adjustments_made": 0,
            "discrepancies_found": 0,
            "timestamp": datetime.now().isoformat()
        }

        # 1. Obtener todos los usuarios
        users = await db_manager.client.user.find_many()
        
        # Intervalo: Ayer completo (o últimas 24h)
        yesterday = datetime.now() - timedelta(days=1)
        start_yt = datetime.combine(yesterday.date(), time.min)
        end_yt   = datetime.combine(yesterday.date(), time.max)

        for user in users:
            try:
                summary["processed_users"] += 1
                
                # 2. Consultar uso oficial en GCloud Monitoring
                # El SDK ya filtra por las labels que inyectamos en cada request
                gcp_usage = await self.gcp_billing.get_usage_by_user(str(user.id), days=1)
                gcp_total_tokens = sum(gcp_usage.values())
                
                if gcp_total_tokens == 0:
                    continue

                # 3. Consultar uso registrado localmente en la base de datos
                local_sessions = await db_manager.client.projectsession.find_many(
                    where={
                        "userId": str(user.id),
                        "createdAt": {"gte": start_yt, "lte": end_yt}
                    }
                )
                local_total_tokens = sum((s.totalTokens or 0) for s in local_sessions)
                
                # 4. Lógica de Reconciliación (Umbral del 1% para evitar ruido)
                diff = abs(gcp_total_tokens - local_total_tokens)
                if local_total_tokens > 0 and (diff / local_total_tokens) > 0.01:
                    summary["discrepancies_found"] += 1
                    logger.warning(f"⚠️ Discrepancia en {user.email}: GCloud={gcp_total_tokens}, Local={local_total_tokens}")
                    
                    # Aplicamos un balance en la sesión más reciente para que el total coincida con la factura
                    if local_sessions:
                        last_session = local_sessions[-1]
                        # Precio promedio conservador para el ajuste (Gemini Flash/Pro mix)
                        delta_cost = (gcp_total_tokens - local_total_tokens) * (0.0001 / 1000)
                        
                        await db_manager.client.projectsession.update(
                            where={"id": last_session.id},
                            data={
                                "totalTokens": (last_session.totalTokens or 0) + (gcp_total_tokens - local_total_tokens),
                                "costEstimate": (last_session.costEstimate or 0) + delta_cost
                            }
                        )
                        summary["adjustments_made"] += 1
                        logger.info(f"✅ Ajuste contable aplicado a sesión {last_session.id}")

            except Exception as e:
                logger.error(f"Error reconciliando usuario {user.email}: {e}")

        return summary

# Singleton
bill_recon = BillingReconciliation()
