# main.py
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

from database.session import engine, Base
import database.models

from api.routes_publish import router as publish_router
from api.routes_oauth import router as oauth_router
from services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("===================================================")
    print("🚀 EVO OMNI PUBLISHER ENGINE - Starting Up...")
    print("===================================================")

    try:
        Base.metadata.create_all(bind=engine)
        print("[Database] PostgreSQL tables verified/created successfully.")
    except Exception as e:
        print(f"[Database Error] Check your connection: {e}")

    # Start the background worker
    start_scheduler()

    yield

    print("\n[System] Shutting down EVO Omni Publisher Engine gracefully...")
    stop_scheduler()


app = FastAPI(
    title="Evo Omni Publisher Engine API",
    description="Multi-Tenant Automated Social Media Publisher",
    version="1.0.0",
    lifespan=lifespan
)

# --- INCLUDE ROUTERS ---
app.include_router(publish_router)
app.include_router(oauth_router)


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "online", "engine": "evo_omni_publisher_engine"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)