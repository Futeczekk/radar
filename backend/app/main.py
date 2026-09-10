from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.scan import router as scan_router
from app.core.database import init_db


app = FastAPI()

init_db()

app.include_router(health_router)
app.include_router(scan_router)
