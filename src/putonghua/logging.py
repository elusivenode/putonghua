"""Logging bootstrap."""

import logging


def configure_logging(level: str) -> None:
    """Configure standard library logging."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s %(name)s %(message)s",
    )
