"""Global error handling middleware."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from jose import JWTError
import logging
import traceback

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors in request data."""
    details = []
    for error in exc.errors():
        error_location = " -> ".join(str(loc) for loc in error["loc"])
        error_msg = error["msg"]
        details.append(f"{error_location}: {error_msg}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": details}
    )


async def jwt_exception_handler(request: Request, exc: JWTError):
    """Handle JWT validation errors."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Invalid authentication credentials"},
        headers={"WWW-Authenticate": "Bearer"}
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors."""
    error_msg = str(exc)
    error_traceback = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error(f"Database error: {error_msg}\n{error_traceback}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred. Please try again later."}
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    error_msg = str(exc)
    error_traceback = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error(f"Unhandled exception: {error_msg}\n{error_traceback}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."}
    )


def add_error_handlers(app: FastAPI):
    """Add error handlers to the application."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(JWTError, jwt_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
