from fastapi import FastAPI

from app.routers import auth, seasons, matches, matches_sync

app = FastAPI(
    title="Taken API",
    description="Duty scheduling backend for US Basketball Amsterdam",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(seasons.router)
app.include_router(matches.router)
app.include_router(matches_sync.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
