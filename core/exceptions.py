class AgentError(Exception):
    """Error base para todos los agentes."""
    pass

class ToolError(AgentError):
    """Error en una tool externa (Notion, GitHub, etc)."""
    pass

class ConfigError(AgentError):
    """Error de configuración o credenciales."""
    pass