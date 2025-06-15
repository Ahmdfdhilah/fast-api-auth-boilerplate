"""Common schemas."""

from pydantic import BaseModel


class StatusMessage(BaseModel):
    """Standard status message response."""
    status: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str


class SuccessResponse(BaseModel):
    """Standard success response."""
    success: bool
    message: str
    data: dict = None
