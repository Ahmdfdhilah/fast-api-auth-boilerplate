"""Request logging middleware."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time
import uuid

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Log request start
        logger.info(f"Request {request_id} started: {request.method} {request.url.path}")
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Log successful response
            process_time = time.time() - start_time
            logger.info(
                f"Request {request_id} completed: {request.method} {request.url.path} "
                f"- Status: {response.status_code} - Duration: {process_time:.4f}s"
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
        
        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            logger.error(
                f"Request {request_id} failed: {request.method} {request.url.path} "
                f"- Error: {str(e)} - Duration: {process_time:.4f}s"
            )
            raise


def setup_logging_middleware(app):
    """Setup request logging middleware."""
    app.add_middleware(RequestLoggingMiddleware)


def setup_logging():
    """Setup basic logging configuration."""
    import logging.config
    
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            },
        },
        'handlers': {
            'default': {
                'formatter': 'default',
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stdout',
            },
        },
        'root': {
            'level': 'INFO',
            'handlers': ['default'],
        },
    }
    
    logging.config.dictConfig(LOGGING_CONFIG)
