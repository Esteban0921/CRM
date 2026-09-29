import csv
import datetime
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from audit import record_field_changes
from billing import (
    duplicate_key,
    duplicate_keys,
    invoice_days_in_queue,
    invoice_days_overdue,
    promote_overdue_invoices,
)
from db import get_db
from dependencies import ensure_family_access, get_current_user, require_role
from invoice_state import (
    PUBLISHED_STATES,
    InvoiceStateError,
    ensure_publishable,
    ensure_transition_allowed,
)
from models.audit_log import AuditedEntityType
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.payment import Payment
from models.task import Task, TaskStatus
from models.user import User, UserRole
from notifications.service import (
    PAYMENT_CLAIM_TITLE,
    close_payment_claim_tasks,
    notify_new_family_invoice,
)
from payments import (
    outstanding_for,
    record_payment,
    settle_without_payment_record,
)
from routers.tasks import _with_family_names as _tasks_with_family_names
from schemas.billing import (
    BulkItemError,
    DuplicateGroup,
    FamilyInvoiceBulkResult,
    FamilyInvoiceBulkUpdate,
)
from schemas.family_invoice import FamilyInvoiceRead, FamilyInvoiceUpdate
from schemas.payment import PaymentCreate, PaymentRead
from schemas.task import TaskRead

router = APIRouter(prefix="/family-invoices", tags=["family-invoices"])


def _with_family_names(
    db: Session, invoices: list[FamilyInvoice], *, hide_extracted: bool = False
) -> list[FamilyInvoiceRead]:
    """El tablero kanban (staff) necesita un nombre legible, no un UUID crudo.
    `FamilyInvoice` no tiene `relationship()` a `Family` (estilo del resto del
    proyecto): se resuelve con una sola query extra en vez de N+1.
    TASK-0074: el padre nunca recibe `extracted_data` (RULE-015).
    """
    family_ids = {invoice.family_id for invoice in invoices if invoice.family_id is not None}
    names = (
        dict(db.query(Family.id, Family.name).filter(Family.id.in_(family_ids)).all())
        if family_ids
        else {}
    )
    dupes = duplicate_keys(invoices)
    return [
        FamilyInvoiceRead.model_validate(invoice).model_copy(
            update={
                "family_name": names.get(invoice.family_id),
                "possible_duplicate": duplicate_key(invoice) in dupes,
                "days_in_queue": invoice_days_in_queue(invoice),
                "days_overdue": invoice_days_overdue(invoice),
                **({"extracted_data": None} if hide_extracted else {}),
            }
        )
        for invoice in invoices
    ]


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# Cabecera con el total real, para que el cliente sepa cuanto queda sin cambiar
# la forma de la respuesta (sigue siendo una lista: no rompe a nadie).
TOTAL_HEADER = "X-Total-Count"


@router.get("", response_model=list[FamilyInvoiceRead])
def list_family_invoices(
    response: Response,
    invoice_status: FamilyInvoiceStatus | None = Query(default=None, alias="status"),
    family_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FamilyInvoiceRead]:
    """Listado paginado (TASK-0126, TASK-0113).

    Antes devolvia la tabla entera: con 2.064 facturas eran 315 ms y 1,23 MB de
    payload por peticion, perfectamente lineal, y el cuello no era Postgres
    -0,39 ms de ejecucion- sino cargar todas las filas en el proceso Python y
    pasarlas por Pydantic. Una empresa de 60 familias genera ~700 facturas al
    ano.
    """
    promote_overdue_invoices(db)
    query = _scoped_invoice_query(db, user, invoice_status, family_id)
    if query is None:
        response.headers[TOTAL_HEADER] = "0"
        return []
    response.headers[TOTAL_HEADER] = str(query.order_by(None).count())
    invoices = (
        query.order_by(FamilyInvoice.confidence.asc().nullsfirst(), FamilyInvoice.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return _with_family_names(db, invoices, hide_extracted=user.role == UserRole.PARENT)


def _scoped_invoice_query(
    db: Session,
    user: User,
    invoice_status: FamilyInvoiceStatus | None,
    family_id: uuid.UUID | None = None,
):
    query = db.query(FamilyInvoice)
    if user.role == UserRole.PARENT:
        if user.family_id is None:
            return None
        query = query.filter(
            FamilyInvoice.family_id == user.family_id,
            FamilyInvoice.status != FamilyInvoiceStatus.PENDING_REVIEW,
        )
    elif family_id is not None:
        query = query.filter(FamilyInvoice.family_id == family_id)
    if invoice_status is not None:
        query = query.filter(FamilyInvoice.status == invoice_status)
    return query


@router.get("/duplicates", response_model=list[DuplicateGroup])
def list_duplicate_invoices(
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[DuplicateGroup]:
    _ = staff
    promote_overdue_invoices(db)
    invoices = db.query(FamilyInvoice).all()
    grouped: dict[tuple, list[FamilyInvoice]] = {}
    for invoice in invoices:
        key = duplicate_key(invoice)
        if key is None:
            continue
        grouped.setdefault(key, []).append(invoice)
    family_ids = {key[0] for key, group in grouped.items() if len(group) > 1}
    names = (
        dict(db.query(Family.id, Family.name).filter(Family.id.in_(family_ids)).all())
        if family_ids
        else {}
    )
    result = []
    for (family_id, amount, issue_date), group in grouped.items():
        if len(group) < 2:
            continue
        result.append(
            DuplicateGroup(
                family_id=family_id,
                family_name=names.get(family_id),
                amount=amount,
                issue_date=issue_date,
                invoice_ids=[invoice.id for invoice in group],
            )
        )
    return result


@router.get("/export.csv")
def export_family_invoices_csv(
    invoice_status: FamilyInvoiceStatus | None = Query(default=None, alias="status"),
    family_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """TASK-0055. El padre solo exporta facturas ya publicadas de su familia."""
    promote_overdue_invoices(db)
    query = _scoped_invoice_query(db, user, invoice_status, family_id)
    if query is None:
        invoices: list[FamilyInvoice] = []
    else:
        invoices = query.order_by(FamilyInvoice.issue_date.desc().nullslast()).all()
    rows = _with_family_names(db, invoices)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "familia", "importe", "moneda", "fecha_emision", "fecha_vencimiento", "estado"]
    )
    for invoice in rows:
        writer.writerow(
            [
                str(invoice.id),
                invoice.family_name or "",
                invoice.amount if invoice.amount is not None else "",
                invoice.currency,
                invoice.issue_date.isoformat() if invoice.issue_date else "",
                invoice.due_date.isoformat() if invoice.due_date else "",
                invoice.status.value,
            ]
        )
    filename = "facturas-familias.csv" if user.role != UserRole.PARENT else "mis-facturas.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{invoice_id}", response_model=FamilyInvoiceRead)
def get_family_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FamilyInvoiceRead:
    invoice = db.get(FamilyInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    ensure_family_access(user, invoice.family_id)
    if user.role == UserRole.PARENT and invoice.status == FamilyInvoiceStatus.PENDING_REVIEW:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    return _with_family_names(db, [invoice], hide_extracted=user.role == UserRole.PARENT)[0]


@router.patch("/{invoice_id}", response_model=FamilyInvoiceRead)
def update_family_invoice(
    invoice_id: uuid.UUID,
    payload: FamilyInvoiceUpdate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> FamilyInvoiceRead:
    invoice = db.get(FamilyInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    previous_status = invoice.status
    changes = payload.model_dump(exclude_unset=True)
    effective_status = changes.get("status", invoice.status)
    effective_family_id = changes["family_id"] if "family_id" in changes else invoice.family_id
    effective_amount = changes["amount"] if "amount" in changes else invoice.amount
    effective_issue = changes["issue_date"] if "issue_date" in changes else invoice.issue_date
    effective_due = changes["due_date"] if "due_date" in changes else invoice.due_date

    # Guardia unica: PATCH, /bulk y /confirm-payment pasan todos por aqui
    # (TASK-0100, TASK-0101).
    try:
        ensure_transition_allowed(previous_status, effective_status)
        if effective_status in PUBLISHED_STATES:
            ensure_publishable(
                invoice,
                family_id=effective_family_id,
                amount=effective_amount,
                issue_date=effective_issue,
                due_date=effective_due,
            )
    except InvoiceStateError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT if exc.conflict else status.HTTP_422_UNPROCESSABLE_CONTENT,
            str(exc),
        ) from exc

    before = {field: getattr(invoice, field) for field in changes}
    for field, value in changes.items():
        setattr(invoice, field, value)
    if (
        invoice.status != FamilyInvoiceStatus.PENDING_REVIEW
        and invoice.due_date is None
        and "due_date" not in changes
    ):
        base = invoice.issue_date or datetime.date.today()
        invoice.due_date = base + datetime.timedelta(days=30)
        if "due_date" not in before:
            before["due_date"] = None
            changes["due_date"] = invoice.due_date
    if previous_status != FamilyInvoiceStatus.PAID and invoice.status == FamilyInvoiceStatus.PAID:
        close_payment_claim_tasks(db, invoice)
        # Marcar «pagada» a mano tambien tiene que dejar un cobro: si no, la
        # factura constaria pagada y la suma de pagos seria cero, con lo que su
        # importe desapareceria del cierre del mes (TASK-0157).
        settle_without_payment_record(db, invoice, recorded_by=staff.id)
    record_field_changes(
        db,
        entity_type=AuditedEntityType.FAMILY_INVOICE,
        entity_id=invoice.id,
        editor_id=staff.id,
        before=before,
        after=changes,
    )
    published = (
        previous_status == FamilyInvoiceStatus.PENDING_REVIEW
        and invoice.status != FamilyInvoiceStatus.PENDING_REVIEW
    )
    if published:
        # Encolar, no enviar: el aviso entra en la MISMA transaccion que la
        # publicacion. Antes el envio iba dentro de la peticion envuelto en
        # `except OSError: pass`, asi que con el SMTP caido la factura quedaba
        # publicada, el padre no se enteraba y no habia ni registro ni
        # reintento (TASK-0104).
        notify_new_family_invoice(db, invoice)
    db.commit()
    db.refresh(invoice)
    return _with_family_names(db, [invoice])[0]


@router.post("/bulk", response_model=FamilyInvoiceBulkResult)
def bulk_update_family_invoices(
    payload: FamilyInvoiceBulkUpdate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> FamilyInvoiceBulkResult:
    if payload.status is None and payload.family_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Indica status o family_id")
    changes = {}
    if payload.status is not None:
        changes["status"] = payload.status
    if payload.family_id is not None:
        changes["family_id"] = payload.family_id
    updated = 0
    failed: list[BulkItemError] = []
    # Ids repetidos contaban una misma factura tantas veces como apareciera:
    # `{"updated": 3}` para una sola factura (TASK-0106).
    seen: set[uuid.UUID] = set()
    unique_ids = [i for i in payload.ids if not (i in seen or seen.add(i))]
    for invoice_id in unique_ids:
        try:
            update_family_invoice(
                invoice_id=invoice_id,
                payload=FamilyInvoiceUpdate(**changes),
                db=db,
                staff=staff,
            )
            updated += 1
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "No se pudo actualizar"
            failed.append(BulkItemError(id=invoice_id, detail=detail))
    return FamilyInvoiceBulkResult(updated=updated, failed=failed)


@router.post(
    "/{invoice_id}/claim-payment",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
def claim_payment(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskRead:
    """TASK-0068. El padre avisa; staff confirma en la cola. No marca pagada sola."""
    if user.role != UserRole.PARENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo el padre puede indicar un pago")
    invoice = db.get(FamilyInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    ensure_family_access(user, invoice.family_id)
    if invoice.status == FamilyInvoiceStatus.PENDING_REVIEW:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    if invoice.status == FamilyInvoiceStatus.PAID:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta factura ya consta como pagada")
    if invoice.family_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    marker = f"invoice:{invoice.id}"
    existing = (
        db.query(Task)
        .filter(
            Task.family_id == invoice.family_id,
            Task.status == TaskStatus.PENDING,
            Task.title == PAYMENT_CLAIM_TITLE,
            Task.description.like(f"{marker}%"),
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay un aviso de pago pendiente")
    amount = f"{invoice.amount} {invoice.currency}" if invoice.amount else "importe por confirmar"
    task = Task(
        family_id=invoice.family_id,
        title=PAYMENT_CLAIM_TITLE,
        description=f"{marker} · {amount}",
        created_by=user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _tasks_with_family_names(db, [task])[0]


@router.post("/{invoice_id}/confirm-payment", response_model=FamilyInvoiceRead)
def confirm_payment(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> FamilyInvoiceRead:
    """TASK-0071. Staff confirma el cobro. Cierra el aviso del padre."""
    invoice = db.get(FamilyInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    if invoice.status == FamilyInvoiceStatus.PENDING_REVIEW:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Publica la factura antes de confirmar el cobro",
        )
    if invoice.status == FamilyInvoiceStatus.PAID:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta factura ya consta como pagada")
    if invoice.family_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Asigna una familia antes de confirmar el cobro",
        )
    return update_family_invoice(
        invoice_id=invoice_id,
        payload=FamilyInvoiceUpdate(status=FamilyInvoiceStatus.PAID),
        db=db,
        staff=staff,
    )


@router.get("/{invoice_id}/payments", response_model=list[PaymentRead])
def list_payments(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Payment]:
    """Cobros de una factura. El padre solo ve los de la suya, y nunca los de
    una factura en revision (RULE-005 / RULE-017).
    """
    invoice = db.get(FamilyInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurso no encontrado")
    ensure_family_access(user, invoice.family_id)
    if user.role == UserRole.PARENT and invoice.status == FamilyInvoiceStatus.PENDING_REVIEW:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurso no encontrado")
    return (
        db.query(Payment).filter(Payment.invoice_id == invoice_id).order_by(Payment.paid_on).all()
    )


@router.post(
    "/{invoice_id}/payments",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_payment(
    invoice_id: uuid.UUID,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Payment:
    """Registra un cobro, total o parcial (TASK-0157).

    Un pago parcial NO salda la factura: sigue viva y su deuda es el resto. Eso
    es justo lo que no se podia expresar cuando `paid` era solo un `status`.
    """
    invoice = db.get(FamilyInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    if invoice.status == FamilyInvoiceStatus.PENDING_REVIEW:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Publica la factura antes de registrar un cobro",
        )
    if invoice.amount is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "La factura no tiene importe: no se puede saber si queda saldada",
        )
    pendiente = outstanding_for(db, invoice)
    if payload.amount > pendiente:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"El cobro ({payload.amount}) supera lo que queda pendiente ({pendiente})",
        )

    before = {"status": invoice.status, "paid_at": invoice.paid_at}
    payment = record_payment(
        db,
        invoice,
        amount=payload.amount,
        paid_on=payload.paid_on or datetime.date.today(),
        method=payload.method,
        reference=payload.reference,
        note=payload.note,
        recorded_by=staff.id,
    )
    # Saldar con un cobro cambia el estado igual que el PATCH, asi que deja el
    # mismo rastro: sin esto el historial no explica quien la dio por pagada.
    record_field_changes(
        db,
        entity_type=AuditedEntityType.FAMILY_INVOICE,
        entity_id=invoice.id,
        editor_id=staff.id,
        before=before,
        after={"status": invoice.status, "paid_at": invoice.paid_at},
    )
    if invoice.status == FamilyInvoiceStatus.PAID:
        close_payment_claim_tasks(db, invoice)
    db.commit()
    db.refresh(payment)
    return payment
