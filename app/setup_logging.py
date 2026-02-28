"""
The module sets up logging configuration for the application.
It configures logging to output messages to both the console and a log file,
with a specified format and logging level.
This should be called at the start of the application to ensure consistent logging behavior.
"""

import logging
import sys


def setup_logging(level=logging.DEBUG, logfile="app.log"):
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d "
        "%(funcName)s() [%(name)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console logs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # File logs (overwrite on each run)
    file_handler = logging.FileHandler(logfile, mode="w")
    file_handler.setFormatter(formatter)

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Remove old handlers to prevent duplicates on re-import
    if root.hasHandlers():
        root.handlers.clear()

    root.addHandler(console_handler)
    root.addHandler(file_handler)
