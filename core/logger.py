import logging
from core.config import settings

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = "[%(asctime)s] %(levelname)s %(name)s — %(message)s"
        handler.setFormatter(logging.Formatter(fmt, "%H:%M:%S"))
        logger.addHandler(handler)
    logger.setLevel(settings.LOG_LEVEL)
    return logger