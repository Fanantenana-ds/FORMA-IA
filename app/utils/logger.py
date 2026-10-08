# ============================================================
# FORMA-IA — LOGGING
# ============================================================

import json
import logging
import os
from datetime import datetime

# Configuration du logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_format = os.getenv("LOG_FORMAT", "text")

# Création du logger
logger = logging.getLogger("formaia")
logger.setLevel(getattr(logging, log_level.upper()))

# Création du handler console
console_handler = logging.StreamHandler()

if log_format == "json":
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": record.levelname,
                "module": record.name,
                "message": record.getMessage()
            }
            if hasattr(record, "extra"):
                log_entry.update(record.extra)
            return json.dumps(log_entry)
    formatter = JSONFormatter()
else:
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Fonction d'utilité
def get_logger(name: str):
    """Retourne un logger avec un nom spécifique"""
    return logger.getChild(name)


_VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def make_vlog(module_logger: logging.Logger):
    """
    Retourne une fonction vlog(msg, level) liée au logger du module appelant.

    Usage :
        logger = logging.getLogger(__name__)
        vlog = make_vlog(logger)
        vlog("message de debug")
    """
    def vlog(msg: str, level: str = "info") -> None:
        if _VERBOSE:
            getattr(module_logger, level)(msg)
    return vlog