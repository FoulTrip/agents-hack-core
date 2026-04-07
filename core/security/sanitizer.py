import re

# Patrones para detección de PII (Personally Identifiable Information)
PATTERNS = {
    "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "secret_token": r"\b(?:ghp_|sk-|secret_|key-)[a-zA-Z0-9]{20,}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "uuid": r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
}

def sanitize_prompt(text: str) -> str:
    """
    Detecta y enmascara información sensible (PII) antes de enviarla a Vertex AI.
    """
    if not text:
        return text

    sanitized = text
    for label, pattern in PATTERNS.items():
        # Reemplazar coincidencias con un placeholder tipo [LABEL_REDACTED]
        sanitized = re.sub(pattern, f"[{label.upper()}_REDACTED]", sanitized)

    return sanitized

def redact_names(text: str) -> str:
    """
    (Opcional) Lógica simple para nombres propios si se detectan patrones.
    En una versión enterprise real, aquí se usaría Google Cloud DLP API
    o una librería de NER (Named Entity Recognition) como Spacy.
    """
    return text
