"""Development server runner for FastAPI application."""

import os
import sys
import uvicorn

if __name__ == "__main__":
    # Ensure we can import from src
    sys.path.append(os.path.dirname(__file__))
    
    # Import and run the app
    from main import app
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )