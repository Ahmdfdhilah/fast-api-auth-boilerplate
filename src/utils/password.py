"""Password security utilities for STEP 1 implementation."""

import secrets
import string
from typing import List
from datetime import datetime, timedelta


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password."""
    if length < 12:
        length = 12
    
    # Ensure we have at least one character from each required category
    lowercase = secrets.choice(string.ascii_lowercase)
    uppercase = secrets.choice(string.ascii_uppercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?")
    
    # Generate remaining characters
    remaining_length = length - 4
    all_chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
    remaining = ''.join(secrets.choice(all_chars) for _ in range(remaining_length))
    
    # Combine and shuffle
    password_list = list(lowercase + uppercase + digit + special + remaining)
    secrets.SystemRandom().shuffle(password_list)
    
    return ''.join(password_list)


def generate_password_reset_token() -> str:
    """Generate secure token for password reset."""
    return secrets.token_urlsafe(32)


def is_password_expired(last_changed: datetime, max_age_days: int = 90) -> bool:
    """Check if password has expired based on age policy."""
    if not last_changed:
        return True
    
    expiry_date = last_changed + timedelta(days=max_age_days)
    return datetime.utcnow() > expiry_date


def get_password_strength_feedback(password: str) -> List[str]:
    """Get user-friendly feedback for password improvement."""
    from src.utils.validators import validate_password_strength
    
    result = validate_password_strength(password)
    feedback = []
    
    if not result["valid"]:
        feedback.extend(result["errors"])
    
    # Add positive feedback based on strength score
    score = result["strength_score"]
    if score >= 80:
        feedback.append("Excellent password strength!")
    elif score >= 60:
        feedback.append("Good password strength.")
    elif score >= 40:
        feedback.append("Fair password strength. Consider making it stronger.")
    else:
        feedback.append("Weak password. Please choose a stronger password.")
    
    return feedback
