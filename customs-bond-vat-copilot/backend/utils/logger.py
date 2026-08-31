"""
Logger — কেন্দ্রীয় লগিং ব্যবস্থা

loguru থাকলে সেটি ব্যবহার করে, না থাকলে standard logging এ ফলব্যাক করে।
এতে development ও production উভয় পরিবেশে কাজ করে।
"""

import sys
from pathlib import Path

try:
    from loguru import logger as _logger

    _HAS_LOGURU = True
except ImportError:
    _HAS_LOGURU = False
    import logging


if _HAS_LOGURU:
    logger = _logger

    def setup_logger(log_file: str = None, level: str = "INFO"):
        """লগার কনফিগার করো"""
        logger.remove()
        # কনসোল আউটপুট
        logger.add(
            sys.stderr,
            level=level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
                "<level>{message}</level>"
            ),
            colorize=True,
        )
        # ফাইল আউটপুট
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            logger.add(
                log_file,
                level=level,
                rotation="10 MB",
                retention="30 days",
                encoding="utf-8",
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            )
        return logger

else:
    # --- Fallback: standard logging ---
    class _LoggerShim:
        """loguru এর মতো আচরণ করে এমন সাধারণ logger"""

        def __init__(self):
            self._log = logging.getLogger("audit_platform")
            self._log.setLevel(logging.INFO)
            if not self._log.handlers:
                h = logging.StreamHandler(sys.stderr)
                h.setFormatter(
                    logging.Formatter(
                        "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                    )
                )
                self._log.addHandler(h)

        def debug(self, msg, *a, **k):
            self._log.debug(str(msg))

        def info(self, msg, *a, **k):
            self._log.info(str(msg))

        def success(self, msg, *a, **k):
            self._log.info(f"✅ {msg}")

        def warning(self, msg, *a, **k):
            self._log.warning(str(msg))

        def error(self, msg, *a, **k):
            self._log.error(str(msg))

        def critical(self, msg, *a, **k):
            self._log.critical(str(msg))

        def exception(self, msg, *a, **k):
            self._log.exception(str(msg))

        def add(self, *a, **k):
            return None

        def remove(self, *a, **k):
            return None

    logger = _LoggerShim()

    def setup_logger(log_file: str = None, level: str = "INFO"):
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s"
                )
            )
            logger._log.addHandler(fh)
        logger._log.setLevel(getattr(logging, level.upper(), logging.INFO))
        return logger


__all__ = ["logger", "setup_logger"]
