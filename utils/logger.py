import logging
import sys
from datetime import datetime

class SCADALogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SCADALogger, cls).__new__(cls)
            cls._instance._configure_logger()
        return cls._instance

    def _configure_logger(self):
        self.logger = logging.getLogger("AquaPunoLogger")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        self.log_buffer = []

    def log(self, level: int, message: str):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        level_name = logging.getLevelName(level)
        formatted_msg = f"{timestamp} [{level_name}] {message}"
        self.log_buffer.append(formatted_msg)
        if len(self.log_buffer) > 1000:
            self.log_buffer.pop(0)
        self.logger.log(level, message)

    def info(self, message: str): self.log(logging.INFO, message)
    def warning(self, message: str): self.log(logging.WARNING, message)
    def error(self, message: str): self.log(logging.ERROR, message)
    def debug(self, message: str): self.log(logging.DEBUG, message)
    def get_buffer(self): return self.log_buffer
    def clear_buffer(self): self.log_buffer.clear()

logger = SCADALogger()
