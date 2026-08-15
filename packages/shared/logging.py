import logging
import sys


def configure_logging(component: str) -> logging.Logger:
    """Structured-ish logging shared by apps/api and apps/worker.

    Format includes the component name so logs from api/worker/scanner can be
    told apart when running under docker-compose (docs/blueprint/12-roadmap.md
    Phase 1 acceptance criteria: "logs funcionam (estruturados, por componente)").
    """
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | " + component + " | %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    return logging.getLogger(component)
