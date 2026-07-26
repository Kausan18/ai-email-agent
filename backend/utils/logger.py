import logging
import sys
from backend.config import settings


# ---------------------------------------------------------------------------
# Logger Setup
# ---------------------------------------------------------------------------
# One logger for the entire application.
# Format: timestamp | level | module | message
#
# Example output:
#   2025-07-23 10:30:01 | INFO     | classifier    | Email mock_001 → recruiter (conf: 1.00)
#   2025-07-23 10:30:01 | INFO     | ollama_client | Generating reply for mock_001
#   2025-07-23 10:30:03 | INFO     | ollama_client | Done in 1842ms
#   2025-07-23 10:30:03 | WARNING  | classifier    | Low confidence on mock_006 (conf: 0.40)
#
# In DEBUG mode (set in config.py) you also see debug-level logs which
# include things like the full prompt sent to Ollama.
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger for a module.

    Usage in any module:
        from backend.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
        logger.warning("Low confidence")
        logger.error("Ollama unreachable")
    """

    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if get_logger is called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Console handler — outputs to terminal
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger