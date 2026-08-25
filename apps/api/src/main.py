from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import health

app = FastAPI(title="CRM Transporte API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
