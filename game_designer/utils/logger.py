"""Loguru tabanlı merkezi loglama yapılandırması."""

import sys
from pathlib import Path
from loguru import logger
from game_designer.config import get_settings


def configure_logger(log_level: str = "INFO") -> None:
    """Merkezi logger ayarlarını yapılandırır."""
    settings = get_settings()
    log_dir = settings.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    # Önceki tüm varsayılan handler'ları kaldır
    logger.remove()

    # Konsol çıktısı (pythonw.exe altında sys.stderr None olabilir)
    if sys.stderr is not None:
        try:
            logger.add(
                sys.stderr,
                level=log_level,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                colorize=True,
            )
        except Exception:
            pass

    # Dosya logu - dönen (rotating) log
    log_file = log_dir / "game_designer.log"
    logger.add(
        str(log_file),
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


# İlk importta yapılandır
configure_logger()

__all__ = ["logger", "configure_logger"]
