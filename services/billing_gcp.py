import os
import logging
from typing import Dict, Any, List
from google.cloud import monitoring_v3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GCPBillingService:
    """
    Saca el uso REAL de tokens y costos usando el SDK de Google Cloud Monitoring.
    Requiere que los pedidos a Vertex AI tengan el label: 'user_id'.
    """
    
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.client = monitoring_v3.MetricServiceClient()
        self.project_name = f"projects/{self.project_id}"

    async def get_usage_by_user(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Consulta las métricas de Vertex AI (Token Count) filtradas por el label 'user_id'
        usando el SDK de Google Cloud Monitoring.
        """
        if not self.project_id:
            logger.error("GOOGLE_CLOUD_PROJECT no configurado.")
            return {}

        now = datetime.utcnow()
        start_time = now - timedelta(days=days)
        
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(now.timestamp())},
            "start_time": {"seconds": int(start_time.timestamp())}
        })

        # Filtro para obtener tokens usados por usuario (si se enviaron con labels)
        results = {}
        metrics = [
            "vertexai.googleapis.com/generative_ai/tokens/usage_count",
        ]

        for metric in metrics:
            # GCP Metric filter by model and user_id label
            filter_str = (
                f'metric.type = "{metric}" AND '
                f'metadata.user_labels.user_id = "{user_id}"'
            )
            
            try:
                pages = self.client.list_time_series(
                    request={
                        "name": self.project_name,
                        "filter": filter_str,
                        "interval": interval,
                        "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    }
                )
                
                total_tokens = 0
                for series in pages:
                    for point in series.points:
                        total_tokens += point.value.int64_value
                
                results[metric] = total_tokens
            except Exception as e:
                logger.error(f"Error consultando Monitoring para {user_id}: {e}")
        
        return results

    @staticmethod
    def get_estimated_usd(tokens: int, model: str) -> float:
        """Helper para convertir tokens a USD real según rates de Vertex AI"""
        # Rates aproximados según Model Garden/GCloud
        rates = {
            "gemini-1.5-pro": 0.00125 / 1000, # Input approx
            "gemini-1.5-flash": 0.00001875 / 1000,
            "sonnet": 0.003 / 1000
        }
        for k, v in rates.items():
            if k in model.lower(): return tokens * v
        return tokens * (0.0005 / 1000) # Fallback

# Nota: Para que esto funcione, el dispatcher de ADK debe incluir el label en el LLM call.
