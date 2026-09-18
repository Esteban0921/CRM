from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

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
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Total-Count"],
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-site",
}

# Respuestas que llevan datos de familias o de menores: nunca a una cache
# intermedia ni al disco del navegador (RULE-015, TASK-0098).
NO_STORE_PREFIXES = ("/families", "/students", "/documents", "/family-invoices", "/search")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    if request.url.path.startswith(NO_STORE_PREFIXES):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(OperationalError)
async def database_unavailable(_request, _exc: OperationalError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "Base de datos no disponible"},
    )


@app.exception_handler(IntegrityError)
async def integrity_conflict(_request, _exc: IntegrityError) -> JSONResponse:
    """Una FK inexistente o un unico duplicado son culpa de la peticion, no del
    servidor: 409 en vez de 500. De paso el traceback deja de llegar al log con
    los parametros de la sentencia (TASK-0093).
    """
    return JSONResponse(
        status_code=409,
        content={"detail": "La operacion entra en conflicto con los datos existentes"},
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
