"""Shared logger helper.

All logging in ContextIngest API flows through this function so log configuration
lives in exactly one place. Callers never construct handlers or read env vars
themselves.
"""

import logging

from configs.common import CommonConfig


def get_logger(name: str) -> logging.Logger:
    """Return a logger with a single stream handler attached at most once."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(CommonConfig.LOG_LEVEL)
    return logger
