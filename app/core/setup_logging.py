import logging
from datetime import datetime
from pathlib import Path


def setup_logging(
    level=logging.DEBUG,
    log_dir: str = "logs",
    keep_last: int = 5,
    suppress_external: bool = True,
):
    """Define a logging configuration that logs to both console and file with a detailed
    format.

    Parameters
    ----------
    level : int, optional
        Logging level (e.g., logging.DEBUG, logging.INFO), by default logging.DEBUG
    log_dir : str, optional
        Directory where log files will be stored, by default "logs"
    keep_last : int, optional
        Number of recent log files to keep, by default 5
    suppress_external : bool, optional
        Whether to suppress verbose logging from external libraries, by default True
    """

    # Ensure log directory exists and create a timestamped log file
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logfile = Path(log_dir) / f"{timestamp}.log"

    # Define a detailed log format
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d "
        "%(funcName)s() [%(name)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Define handlers for console and file output
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file = logging.FileHandler(logfile)
    file.setFormatter(formatter)

    # Set up the root logger with the specified level and handlers
    root = logging.getLogger()
    root.setLevel(level)
    if root.hasHandlers():
        root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file)

    # Suppress verbose logging from external libraries if requested
    NOISY_LOGGERS = [
        "mlflow",
        "mlflow.store",
        "mlflow.store.db",
        "mlflow.store.db.utils",
        "alembic",
        "alembic.runtime",
        "alembic.runtime.migration",
        "sqlalchemy",
        "git",
        "urllib3.connectionpool",
        "google.auth._default",
        "matplotlib.font_manager",
        "pandas_gbq.gbq_connector",
        "httpx",
    ]

    if suppress_external:
        for name in NOISY_LOGGERS:
            logger = logging.getLogger(name)
            logger.handlers.clear()
            logger.setLevel(logging.WARNING)
            logger.propagate = True

    # Clean up old log files, keeping only the most recent ones
    log_files = sorted(
        Path(log_dir).glob("*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old_file in log_files[keep_last:]:
        old_file.unlink()
