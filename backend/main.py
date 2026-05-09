import uvicorn
from api.app import app
from config import settings

if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
