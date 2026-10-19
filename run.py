from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.getenv("PORT", 5000))

    uvicorn.run("run:app", host="0.0.0.0", port=port, reload=Config.DEBUG)
