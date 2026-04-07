from google import genai
from core.logger import get_logger

logger = get_logger(__name__)

def generate_embedding(text: str) -> list[float]:
    """
    Genera un vector de embedding (768 dimensiones) utilizando
    el modelo de Google GenAI para búsqueda semántica.
    """
    try:
        # Se asume que GOOGLE_API_KEY / credenciales de Vertex están configuradas.
        client = genai.Client()
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=text
        )
        # Retorna el vector de floats
        return response.embeddings[0].values
    except Exception as e:
        logger.error(f"Error generando embedding vectorial: {e}")
        return []
