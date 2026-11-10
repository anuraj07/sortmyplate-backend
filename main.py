import os
import uvicorn
from app.main import app  # Re-export FastAPI application instance

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
