"""Console logging and bounded UTF-8 log files for command-line jobs."""

import logging
from logging.handlers import RotatingFileHandler

from .paths import LOG_DIR


def configure_logging() -> None:
    root = logging.getLogger()
    if any(getattr(handler, "_law_push", False) for handler in root.handlers):
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handlers = [logging.StreamHandler(), RotatingFileHandler(
        LOG_DIR / "law-push.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")]
    for handler in handlers:
        handler.setFormatter(formatter)
        handler._law_push = True
        root.addHandler(handler)
    root.setLevel(logging.INFO)
