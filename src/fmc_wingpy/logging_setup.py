#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Logging setup with rotating file handler and secure permissions.

Provides:
- Rotating file handler (10 MB per file, 5 backups)
- Console handler for interactive feedback
- Log file permissions set to 0640 (no world access)
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from fmc_wingpy.config import ConfigManager


def setup_logging(
    log_file: Optional[Path] = None,
    logger_name: str = "fmc_wingpy",
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console: bool = True,
) -> logging.Logger:
    """Configure logging with rotating file handler and optional console output."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    log_format = "[%(asctime)s] %(levelname)-8s %(name)s  %(message)s"
    formatter = logging.Formatter(log_format)

    if log_file is None:
        log_file = ConfigManager.get_log_file()

    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Restrict log file permissions (no world access) — ADR-002 §7.6
    try:
        os.chmod(log_file, 0o640)
    except OSError:
        pass

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger with the given name."""
    return logging.getLogger(name)
