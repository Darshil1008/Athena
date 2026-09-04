"""
logger.py

Central logging system for Project Athena.
"""

from datetime import datetime


class Logger:
    """
    Simple console logger.

    Every message printed by Athena should
    go through this logger.
    """

    @staticmethod
    def _log(level: str, message: str):

        current_time = datetime.now().strftime("%H:%M:%S")

        print(f"[{current_time}] [{level}] {message}")

    @staticmethod
    def info(message: str):
        Logger._log("INFO", message)

    @staticmethod
    def warning(message: str):
        Logger._log("WARNING", message)

    @staticmethod
    def error(message: str):
        Logger._log("ERROR", message)