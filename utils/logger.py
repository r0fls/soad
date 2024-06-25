# utils/json_logger.py
import logging
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if record.levelno >= logging.ERROR:
            log_record['lineno'] = record.lineno
            log_record['pathname'] = record.pathname

class JsonLogger:
    def __init__(self, log_file='app.log'):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Create handlers
        file_handler = logging.FileHandler(log_file)
        console_handler = logging.StreamHandler()

        # Create formatters and add it to handlers
        formatter = CustomJsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to the logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def get_logger(self):
        return self.logger

# Create a logger instance
logger = JsonLogger().get_logger()
