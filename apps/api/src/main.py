from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import (
    auth,
    contracts,
    families,
    family_invoices,
    health,
    notes,
    students,
    supplier_invoices,
    tasks,
    users,
)

app = FastAPI(title="CRM Transporte API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(families.router)
app.include_router(students.router)
app.include_router(contracts.router)
app.include_router(family_invoices.router)
app.include_router(supplier_invoices.router)
app.include_router(notes.router)
app.include_router(tasks.router)
