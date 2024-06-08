# utils/json_logger.py
import logging
import os
from pythonjsonlogger import jsonlogger

class JsonLogger:
    def __init__(self, log_file='app.log'):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        # Create handlers
        file_handler = logging.FileHandler(log_file)
        console_handler = logging.StreamHandler()

        # Create formatters and add it to handlers
        formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to the logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def get_logger(self):
        return self.logger

# Create a logger instance
logger = JsonLogger().get_logger()
