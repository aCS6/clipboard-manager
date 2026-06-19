import logging
import sys

_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE = "%H:%M:%S"

logging.basicConfig(stream=sys.stderr, format=_FMT, datefmt=_DATE, level=logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
