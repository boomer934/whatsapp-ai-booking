"""Configurazione del logging applicativo."""

import logging


def setup_logging(level: str = "INFO") -> None:
    """Imposta un formato di log uniforme per l'app e uvicorn."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
