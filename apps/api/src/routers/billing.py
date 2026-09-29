import csv
import io
from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from billing import (
    expected_fees_by_family,
    invoice_is_due_soon,
    invoice_is_outstanding,
    invoice_is_overdue,
    invoice_outstanding,
    month_bounds,
    promote_overdue_invoices,
    unbilled_by_family,
    unbilled_task_title,
)
from db import get_db
from dependencies import require_role
from models.contract import Contract, ContractStatus
from models.email import Email, EmailProcessingStatus
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.task import Task, TaskStatus
from models.user import User, UserRole
from payments import collected_between, collected_between_by_family
from schemas.billing import (
    AtRiskFamily,
    FamilyMonthRow,
    MonthReport,
    StaffBillingSummary,
    UnbilledFamily,
    UnbilledTasksResult,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/summary", response_model=StaffBillingSummary)
def staff_billing_summary(
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> StaffBillingSummary:
    promote_overdue_invoices(db)
    invoices = db.query(FamilyInvoice).all()
    pending = sum(1 for invoice in invoices if invoice.status == FamilyInvoiceStatus.PENDING_REVIEW)
    overdue_invoices = [invoice for invoice in invoices if invoice_is_overdue(invoice)]
    outstanding = [invoice for invoice in invoices if invoice_is_outstanding(invoice)]
    due_soon = [invoice for invoice in invoices if invoice_is_due_soon(invoice)]
    families_with_debt = {
        invoice.family_id for invoice in outstanding if invoice.family_id is not None
    }
    month_start, month_end = month_bounds()
    expected = sum(
        (
            contract.monthly_fee
            for contract in db.query(Contract)
            .filter(Contract.status == ContractStatus.ACTIVE)
            .all()
            if contract.start_date <= month_end
            and (contract.end_date is None or contract.end_date >= month_start)
        ),
        Decimal("0.00"),
    )
    # Por fecha de COBRO, no de emision (TASK-0102): un cobro de septiembre
    # sobre una factura de agosto era invisible en septiembre y cambiaba
    # retroactivamente el cierre de agosto.
    collected = collected_between(db, month_start, month_end)
    today = date.today()
    return StaffBillingSummary(
        pending_review_count=pending,
        overdue_count=len(overdue_invoices),
        families_with_debt=len(families_with_debt),
        families_count=db.query(Family).count(),
        overdue_amount=sum(
            (invoice_outstanding(invoice) for invoice in overdue_invoices), Decimal("0.00")
        ),
        outstanding_amount=sum(
            (invoice_outstanding(invoice) for invoice in outstanding), Decimal("0.00")
        ),
        year_month=f"{today.year:04d}-{today.month:02d}",
        expected_amount=expected,
        collected_amount=collected,
        due_soon_count=len(due_soon),
        due_soon_amount=sum(
            (invoice_outstanding(invoice) for invoice in due_soon), Decimal("0.00")
        ),
        pending_tasks=db.query(Task).filter(Task.status == TaskStatus.PENDING).count(),
        failed_emails=db.query(Email)
        .filter(Email.processing_status == EmailProcessingStatus.FAILED)
        .count(),
        unbilled_families=len(unbilled_by_family(db)),
    )


@router.get("/at-risk", response_model=list[AtRiskFamily])
def list_at_risk_families(
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[AtRiskFamily]:
    promote_overdue_invoices(db)
    invoices = db.query(FamilyInvoice).all()
    overdue_by_family: dict = defaultdict(list)
    for invoice in invoices:
        if invoice.family_id and invoice_is_overdue(invoice):
            overdue_by_family[invoice.family_id].append(invoice)
    if not overdue_by_family:
        return []
    families = {
        family.id: family
        for family in db.query(Family).filter(Family.id.in_(overdue_by_family.keys())).all()
    }
    pending_tasks = db.query(Task).filter(Task.status == TaskStatus.PENDING).all()
    tasks_by_family: dict = defaultdict(int)
    for task in pending_tasks:
        tasks_by_family[task.family_id] += 1
    result = []
    for family_id, group in overdue_by_family.items():
        family = families.get(family_id)
        if family is None:
            continue
        result.append(
            AtRiskFamily(
                id=family.id,
                name=family.name,
                overdue_amount=sum((invoice_outstanding(i) for i in group), Decimal("0.00")),
                overdue_count=len(group),
                pending_tasks=tasks_by_family[family_id],
            )
        )
    result.sort(key=lambda item: item.overdue_amount, reverse=True)
    return result[:20]


@router.get("/unbilled", response_model=list[UnbilledFamily])
def list_unbilled_families(
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> list[UnbilledFamily]:
    gaps = unbilled_by_family(db)
    if not gaps:
        return []
    families = {
        family.id: family for family in db.query(Family).filter(Family.id.in_(gaps.keys())).all()
    }
    result = [
        UnbilledFamily(id=family_id, name=families[family_id].name, expected_amount=amount)
        for family_id, amount in gaps.items()
        if family_id in families
    ]
    result.sort(key=lambda item: item.name)
    return result


@router.post("/unbilled/tasks", response_model=UnbilledTasksResult)
def create_unbilled_tasks(
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> UnbilledTasksResult:
    """TASK-0083. Una tarea por hueco del mes; no duplica si ya está pendiente."""
    gaps = unbilled_by_family(db)
    title = unbilled_task_title()
    created = 0
    skipped = 0
    for family_id, amount in gaps.items():
        existing = (
            db.query(Task)
            .filter(
                Task.family_id == family_id,
                Task.status == TaskStatus.PENDING,
                Task.title == title,
            )
            .first()
        )
        if existing is not None:
            skipped += 1
            continue
        db.add(
            Task(
                family_id=family_id,
                title=title,
                description=f"Cuota esperada {amount} EUR",
                created_by=staff.id,
            )
        )
        created += 1
    if created:
        db.commit()
    today = date.today()
    return UnbilledTasksResult(
        created=created,
        skipped=skipped,
        year_month=f"{today.year:04d}-{today.month:02d}",
    )


@router.get("/month-report", response_model=MonthReport)
def staff_month_report(
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> MonthReport:
    """TASK-0072. Cierre del mes: esperado, cobrado, deuda y huecos por familia."""
    promote_overdue_invoices(db)
    today = date.today()
    start, end = month_bounds(today)
    expected = expected_fees_by_family(db)
    gaps = unbilled_by_family(db)
    invoices = db.query(FamilyInvoice).filter(FamilyInvoice.family_id.isnot(None)).all()
    collected: dict = defaultdict(lambda: Decimal("0.00"))
    outstanding: dict = defaultdict(lambda: Decimal("0.00"))
    overdue: dict = defaultdict(lambda: Decimal("0.00"))
    for family_id, importe in collected_between_by_family(db, start, end).items():
        collected[family_id] += importe
    for invoice in invoices:
        family_id = invoice.family_id
        if invoice_is_outstanding(invoice):
            outstanding[family_id] += invoice_outstanding(invoice)
        if invoice_is_overdue(invoice):
            overdue[family_id] += invoice_outstanding(invoice)
    family_ids = set(expected) | set(collected) | set(outstanding) | set(overdue)
    families = (
        {family.id: family for family in db.query(Family).filter(Family.id.in_(family_ids)).all()}
        if family_ids
        else {}
    )
    rows = []
    for family_id in family_ids:
        family = families.get(family_id)
        if family is None:
            continue
        rows.append(
            FamilyMonthRow(
                id=family_id,
                name=family.name,
                expected_amount=expected.get(family_id, Decimal("0.00")),
                collected_amount=collected[family_id],
                outstanding_amount=outstanding[family_id],
                overdue_amount=overdue[family_id],
                unbilled=family_id in gaps,
            )
        )
    rows.sort(key=lambda item: item.name)
    return MonthReport(year_month=f"{today.year:04d}-{today.month:02d}", families=rows)


@router.get("/month-report.csv")
def export_month_report_csv(
    db: Session = Depends(get_db),
    staff: User = Depends(require_role(UserRole.STAFF, UserRole.ADMIN)),
) -> Response:
    """TASK-0078. Mismas filas que el informe, para Excel."""
    report = staff_month_report(db, staff)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["familia", "esperado", "cobrado", "deuda", "vencido", "sin_facturar", "moneda"]
    )
    for row in report.families:
        writer.writerow(
            [
                row.name,
                row.expected_amount,
                row.collected_amount,
                row.outstanding_amount,
                row.overdue_amount,
                "si" if row.unbilled else "no",
                row.currency,
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="cierre-{report.year_month}.csv"'},
    )
