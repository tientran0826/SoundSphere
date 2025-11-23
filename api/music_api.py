from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import albums, bot_control, config, history, queue

app = FastAPI(
    title="SpareSphere Music API",
    description="API for managing music playback and albums in SpareSphere Discord Bot",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(queue.router)
app.include_router(albums.router)
app.include_router(history.router)
app.include_router(config.router)
app.include_router(bot_control.router)


@app.get("/")
async def root():
    return {
        "message": "Welcome to SpareSphere Music API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Music API is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
