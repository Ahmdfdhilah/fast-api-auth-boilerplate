"""Logging configuration utilities."""

import logging
import logging.handlers
import json
import os
from datetime import datetime

from src.core.config import settings


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self, service_name):
        super().__init__()
        self.service_name = service_name

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry['exc_info'] = self.formatException(record.exc_info)
        if record.stack_info:
            log_entry['stack_info'] = self.formatStack(record.stack_info)
            
        return json.dumps(log_entry)


def setup_logging():
    """Setup application logging."""
    import logging.config
    
    # Create logs directory
    try:
        os.makedirs(settings.LOG_DIRECTORY, exist_ok=True)
    except OSError as e:
        print(f"Error creating log directory: {e}")

    log_file_path = os.path.join(settings.LOG_DIRECTORY, f'{settings.SERVICE_NAME}.log')
    
    # Logging configuration
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': 'src.utils.logging.JSONFormatter',
                'service_name': settings.SERVICE_NAME,
            },
            'simple': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'simple',
                'stream': 'ext://sys.stdout',
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'INFO',
                'formatter': 'json',
                'filename': log_file_path,
                'maxBytes': settings.LOG_MAX_BYTES,
                'backupCount': settings.LOG_BACKUP_COUNT,
                'encoding': 'utf-8',
            },
        },
        'loggers': {
            '': {  # Root logger
                'level': 'INFO',
                'handlers': ['console', 'file'],
                'propagate': False,
            },
            'uvicorn': {
                'level': 'INFO',
                'handlers': ['console', 'file'],
                'propagate': False,
            },
            'uvicorn.access': {
                'level': 'INFO',
                'handlers': ['console', 'file'],
                'propagate': False,
            },
        },
    }
    
    try:
        logging.config.dictConfig(LOGGING_CONFIG)
    except Exception as e:
        print(f"Error setting up logging configuration: {e}")
        # Fallback to basic config
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file_path) if os.path.exists(settings.LOG_DIRECTORY) else logging.StreamHandler()
            ]
        )
