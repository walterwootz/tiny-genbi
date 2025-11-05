"""
Main entry point for the Tiny GenBI service.
"""

import sys
import uvicorn
from config import settings

def main():
    """Start the Tiny GenBI API service."""
    print("=" * 60)
    print("🚀 Starting Tiny GenBI Service")
    print("=" * 60)
    print(f"Host: {settings.api_host}")
    print(f"Port: {settings.api_port}")
    print(f"LLM Model: {settings.llm_model}")
    print(f"Debug Mode: {settings.debug}")
    print("=" * 60)
    print()
    print("📚 API Documentation: http://localhost:5556/docs")
    print("🏥 Health Check: http://localhost:5556/health")
    print()
    print("Press CTRL+C to stop the service")
    print("=" * 60)
    
    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )

if __name__ == "__main__":
    main()
