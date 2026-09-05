from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


LOGGER_NAME = "carpan_muhasebe_asistani"


def configure_logging(data_root: Path) -> logging.Logger:
    """Uygulama günlüklerini kullanıcıya ait kalıcı klasöre yönlendirir."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    log_dir = Path(data_root) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "uygulama.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def install_exception_logging(logger: logging.Logger) -> None:
    """Yakalanmamış ana iş parçacığı hatalarını günlükte saklar."""
    original_hook = sys.excepthook

    def _log_exception(exc_type, exc_value, traceback) -> None:
        logger.critical(
            "Yakalanmamış uygulama hatası",
            exc_info=(exc_type, exc_value, traceback),
        )
        original_hook(exc_type, exc_value, traceback)

    sys.excepthook = _log_exception
