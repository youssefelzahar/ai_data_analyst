import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(debug: bool = False) -> None:
    """Configure root logging for the whole application."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format=LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )
    # Uvicorn installs its own handlers; align their levels with ours.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).setLevel(logging.DEBUG if debug else logging.INFO)
