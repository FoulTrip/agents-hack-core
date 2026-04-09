import os
from core.logger import get_logger

logger = get_logger(__name__)

def setup_adk_vertex():
    """
    Configura el ADK para usar Vertex AI y registra el soporte para Claude.
    """
    try:
        # Eliminamos la configuración estricta global. El Dispatcher lo manejará.
        # os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        
        # Intentar registrar Claude si la librería está disponible
        from google.adk.models.anthropic_llm import Claude
        from google.adk.models.registry import LLMRegistry
        
        LLMRegistry.register(Claude)
        logger.info("ADK configurado con Vertex AI y soporte para Claude registrado.")
    except ImportError:
        logger.warning("No se pudo registrar Claude en ADK (¿Falta anthropic[vertex]?). Asegúrate de que las dependencias estén instaladas.")
    except Exception as e:
        logger.error(f"Error configurando ADK Vertex: {e}")

if __name__ == "__main__":
    setup_adk_vertex()
