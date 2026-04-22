# Why this exists: one formatter everywhere so logs from the scheduler,
# routes, and pipeline all read the same.
import logging
import sys

_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        handler = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s :: %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(fmt)
        root = logging.getLogger()
        root.handlers = [handler]
        root.setLevel(logging.INFO)
        _configured = True
    return logging.getLogger(name)
