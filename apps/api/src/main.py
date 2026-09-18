from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from config import settings
from routers import (
    auth,
    billing,
    contracts,
    documents,
    emails,
    families,
    family_invoices,
    health,
    ingestion,
    notes,
    notifications,
    search,
    students,
    supplier_invoices,
    suppliers,
    tasks,
    users,
)

app = FastAPI(title="CRM Transporte API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(OperationalError)
async def database_unavailable(_request, _exc: OperationalError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "Base de datos no disponible"},
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(families.router)
app.include_router(students.router)
app.include_router(contracts.router)
app.include_router(family_invoices.router)
app.include_router(supplier_invoices.router)
app.include_router(suppliers.router)
app.include_router(notes.router)
app.include_router(tasks.router)
app.include_router(ingestion.router)
app.include_router(documents.router)
app.include_router(billing.router)
app.include_router(notifications.router)
app.include_router(search.router)
app.include_router(emails.router)
