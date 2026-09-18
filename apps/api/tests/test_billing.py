import datetime
import uuid
from decimal import Decimal

from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _invoice(db_session, family_id, *, status, amount, due_date=None, issue_date=None):
    email = Email(gmail_id=f"bill-{uuid.uuid4()}")
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id, document_type=DocumentType.FAMILY_INVOICE, file_path="f.pdf"
    )
    db_session.add(document)
    db_session.commit()
    invoice = FamilyInvoice(
        document_id=document.id,
        family_id=family_id,
        status=status,
        amount=Decimal(amount),
        due_date=due_date,
        issue_date=issue_date,
    )
    db_session.add(invoice)
    db_session.commit()
    return invoice


def test_family_billing_sums_outstanding_and_hides_pending_from_parent(client, db_session):
    family = Family(name="Familia Deuda")
    db_session.add(family)
    db_session.commit()
    _invoice(db_session, family.id, status=FamilyInvoiceStatus.SENT, amount="45.00")
    _invoice(
        db_session,
        family.id,
        status=FamilyInvoiceStatus.OVERDUE,
        amount="30.00",
        due_date=datetime.date(2026, 1, 1),
    )
    _invoice(db_session, family.id, status=FamilyInvoiceStatus.PENDING_REVIEW, amount="99.00")
    _invoice(db_session, family.id, status=FamilyInvoiceStatus.PAID, amount="10.00")
    parent = User(
        family_id=family.id,
        email="padre-deuda@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    staff = User(
        email="staff-deuda@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add_all([parent, staff])
    db_session.commit()

    as_parent = client.get(f"/families/{family.id}/billing", headers=_auth_header(parent)).json()
    as_staff = client.get(f"/families/{family.id}/billing", headers=_auth_header(staff)).json()

    assert as_parent["outstanding_amount"] == "75.00"
    assert as_parent["overdue_amount"] == "30.00"
    assert as_parent["overdue_count"] == 1
    assert as_parent["paid_count"] == 1
    assert as_staff["outstanding_amount"] == "75.00"


def test_staff_billing_summary(client, db_session):
    family = Family(name="Familia Resumen")
    db_session.add(family)
    db_session.commit()
    _invoice(db_session, family.id, status=FamilyInvoiceStatus.PENDING_REVIEW, amount="10.00")
    _invoice(
        db_session,
        family.id,
        status=FamilyInvoiceStatus.SENT,
        amount="20.00",
        due_date=datetime.date(2020, 1, 1),
    )
    staff = User(
        email="staff-sum@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get("/billing/summary", headers=_auth_header(staff))

    assert response.status_code == 200
    body = response.json()
    assert body["pending_review_count"] == 1
    assert body["overdue_count"] == 1
    assert body["families_with_debt"] == 1
    assert body["overdue_amount"] == "20.00"
    assert "year_month" in body
    assert body["expected_amount"] == "0.00"
    assert body["due_soon_count"] == 0


def test_parent_cannot_read_staff_billing_summary(client, db_session):
    parent = User(
        email="padre-sum@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get("/billing/summary", headers=_auth_header(parent))
    assert response.status_code == 403


def test_billing_summary_expected_from_active_contracts(client, db_session):
    from models.contract import Contract, ContractStatus
    from models.student import Student

    family = Family(name="Familia Cuota")
    db_session.add(family)
    db_session.commit()
    student = Student(family_id=family.id, name="Alumno Cuota")
    db_session.add(student)
    db_session.commit()
    db_session.add(
        Contract(
            student_id=student.id,
            service_type="Ruta",
            monthly_fee=Decimal("45.00"),
            start_date=datetime.date(2026, 1, 1),
            status=ContractStatus.ACTIVE,
        )
    )
    staff = User(
        email="staff-cuota@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    body = client.get("/billing/summary", headers=_auth_header(staff)).json()
    assert body["expected_amount"] == "45.00"


def test_at_risk_families_endpoint(client, db_session):
    family = Family(name="Familia Riesgo")
    db_session.add(family)
    db_session.commit()
    _invoice(
        db_session,
        family.id,
        status=FamilyInvoiceStatus.OVERDUE,
        amount="30.00",
        due_date=datetime.date(2020, 1, 1),
    )
    staff = User(
        email="staff-risk@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    response = client.get("/billing/at-risk", headers=_auth_header(staff))
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Familia Riesgo"
    assert response.json()[0]["overdue_amount"] == "30.00"


def test_duplicate_invoices_are_grouped(client, db_session):
    family = Family(name="Familia Dup")
    db_session.add(family)
    db_session.commit()
    _invoice(db_session, family.id, status=FamilyInvoiceStatus.SENT, amount="40.00")
    first = db_session.query(FamilyInvoice).filter(FamilyInvoice.family_id == family.id).first()
    first.issue_date = datetime.date(2026, 9, 1)
    _invoice(db_session, family.id, status=FamilyInvoiceStatus.SENT, amount="40.00")
    second = (
        db_session.query(FamilyInvoice)
        .filter(FamilyInvoice.family_id == family.id, FamilyInvoice.id != first.id)
        .one()
    )
    second.issue_date = datetime.date(2026, 9, 1)
    db_session.commit()
    staff = User(
        email="staff-dup@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()

    grouped = client.get("/family-invoices/duplicates", headers=_auth_header(staff))
    listed = client.get("/family-invoices", headers=_auth_header(staff)).json()

    assert grouped.status_code == 200
    assert len(grouped.json()) == 1
    assert grouped.json()[0]["amount"] == "40.00"
    assert all(row["possible_duplicate"] for row in listed if row["amount"] == "40.00")


def _active_contract(db_session, family_id, fee="45.00"):
    from models.contract import Contract, ContractStatus
    from models.student import Student

    student = Student(family_id=family_id, name="Alumno Hueco")
    db_session.add(student)
    db_session.commit()
    db_session.add(
        Contract(
            student_id=student.id,
            service_type="Ruta",
            monthly_fee=Decimal(fee),
            start_date=datetime.date(2026, 1, 1),
            status=ContractStatus.ACTIVE,
        )
    )
    db_session.commit()


def test_unbilled_families_are_those_without_an_invoice_this_month(client, db_session):
    gap = Family(name="Familia Hueco")
    billed = Family(name="Familia Al dia")
    db_session.add_all([gap, billed])
    db_session.commit()
    _active_contract(db_session, gap.id, "45.00")
    _active_contract(db_session, billed.id, "50.00")
    today = datetime.date.today()
    _invoice(
        db_session,
        billed.id,
        status=FamilyInvoiceStatus.SENT,
        amount="50.00",
        issue_date=today.replace(day=1),
    )
    last_month = today.replace(day=1) - datetime.timedelta(days=1)
    _invoice(
        db_session,
        gap.id,
        status=FamilyInvoiceStatus.SENT,
        amount="45.00",
        issue_date=last_month,
    )
    staff = User(
        email="staff-hueco@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    parent = User(
        family_id=gap.id,
        email="padre-hueco@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add_all([staff, parent])
    db_session.commit()

    listed = client.get("/billing/unbilled", headers=_auth_header(staff))
    summary = client.get("/billing/summary", headers=_auth_header(staff)).json()
    as_parent = client.get("/billing/unbilled", headers=_auth_header(parent))

    assert listed.status_code == 200
    assert [row["name"] for row in listed.json()] == ["Familia Hueco"]
    assert listed.json()[0]["expected_amount"] == "45.00"
    assert summary["unbilled_families"] == 1
    assert as_parent.status_code == 403


def test_month_report_lists_expected_and_gaps(client, db_session):
    gap = Family(name="Familia Informe Hueco")
    billed = Family(name="Familia Informe Al dia")
    db_session.add_all([gap, billed])
    db_session.commit()
    _active_contract(db_session, gap.id, "45.00")
    _active_contract(db_session, billed.id, "50.00")
    today = datetime.date.today()
    paid = _invoice(
        db_session,
        billed.id,
        status=FamilyInvoiceStatus.PAID,
        amount="50.00",
        issue_date=today.replace(day=1),
    )
    _ = paid
    staff = User(
        email="staff-informe@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    parent = User(
        family_id=gap.id,
        email="padre-informe@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add_all([staff, parent])
    db_session.commit()

    response = client.get("/billing/month-report", headers=_auth_header(staff))
    as_parent = client.get("/billing/month-report", headers=_auth_header(parent))

    assert response.status_code == 200
    body = response.json()
    by_name = {row["name"]: row for row in body["families"]}
    assert by_name["Familia Informe Hueco"]["unbilled"] is True
    assert by_name["Familia Informe Hueco"]["expected_amount"] == "45.00"
    assert by_name["Familia Informe Al dia"]["collected_amount"] == "50.00"
    assert by_name["Familia Informe Al dia"]["unbilled"] is False
    assert as_parent.status_code == 403

    csv_response = client.get("/billing/month-report.csv", headers=_auth_header(staff))
    csv_parent = client.get("/billing/month-report.csv", headers=_auth_header(parent))
    assert csv_response.status_code == 200
    assert "Familia Informe Hueco" in csv_response.text
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert csv_parent.status_code == 403


def test_unbilled_tasks_are_idempotent(client, db_session):
    family = Family(name="Familia Tarea Hueco")
    db_session.add(family)
    db_session.commit()
    _active_contract(db_session, family.id, "45.00")
    staff = User(
        email="staff-hueco-task@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    parent = User(
        family_id=family.id,
        email="padre-hueco-task@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add_all([staff, parent])
    db_session.commit()

    first = client.post("/billing/unbilled/tasks", headers=_auth_header(staff))
    second = client.post("/billing/unbilled/tasks", headers=_auth_header(staff))
    as_parent = client.post("/billing/unbilled/tasks", headers=_auth_header(parent))

    assert first.status_code == 200
    assert first.json()["created"] == 1
    assert second.json()["created"] == 0
    assert second.json()["skipped"] == 1
    assert as_parent.status_code == 403
    tasks = client.get("/tasks", headers=_auth_header(staff)).json()
    assert any(row["title"].startswith("Facturar el mes") for row in tasks)
