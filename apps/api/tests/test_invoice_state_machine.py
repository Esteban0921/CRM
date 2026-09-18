"""Matriz completa de transiciones (TASK-0100, TASK-0101, TASK-0106).

La auditoria comprobo que `paid -> pending_review`, `pending_review -> paid`,
`paid -> sent` y `-> overdue` a mano devolvian todos 200, tambien en lote.
Deshacer un cobro borraba su aporte al mes y ademas escondia la factura al
padre (RULE-017).
"""

import datetime
import uuid
from decimal import Decimal

import pytest

from invoice_state import ALLOWED_TRANSITIONS, InvoiceStateError, ensure_transition_allowed
from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.user import User, UserRole
from security import create_access_token, hash_password

PENDING = FamilyInvoiceStatus.PENDING_REVIEW
SENT = FamilyInvoiceStatus.SENT
PAID = FamilyInvoiceStatus.PAID
OVERDUE = FamilyInvoiceStatus.OVERDUE


def _auth(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _staff(db_session) -> User:
    staff = User(
        email=f"staff-{uuid.uuid4()}@example.com",
        password_hash=hash_password("x"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    return staff


def _invoice(
    db_session, family, status, *, amount=Decimal("45.00"), issue=datetime.date(2026, 9, 1)
):
    email = Email(gmail_id=f"g-{uuid.uuid4()}")
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id, document_type=DocumentType.FAMILY_INVOICE, file_path="f.pdf"
    )
    db_session.add(document)
    db_session.commit()
    invoice = FamilyInvoice(
        document_id=document.id,
        family_id=family.id if family else None,
        status=status,
        amount=amount,
        issue_date=issue,
    )
    db_session.add(invoice)
    db_session.commit()
    return invoice


def _family(db_session) -> Family:
    family = Family(name=f"Familia {uuid.uuid4().hex[:6]}")
    db_session.add(family)
    db_session.commit()
    return family


# --- La matriz 4x4 completa contra la API ---------------------------------


@pytest.mark.parametrize("origen", [PENDING, SENT, PAID, OVERDUE])
@pytest.mark.parametrize("destino", [PENDING, SENT, PAID, OVERDUE])
def test_matriz_de_transiciones(client, db_session, origen, destino):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, origen)

    response = client.patch(
        f"/family-invoices/{invoice.id}",
        headers=_auth(staff),
        json={"status": destino.value},
    )

    permitida = destino in ALLOWED_TRANSITIONS[origen]
    if permitida:
        assert response.status_code == 200, (origen, destino, response.text)
        assert response.json()["status"] == destino.value
    else:
        assert response.status_code == 409, (origen, destino, response.text)


def test_una_factura_cobrada_no_se_descobra(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, PAID)

    for destino in (PENDING, SENT, OVERDUE):
        response = client.patch(
            f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": destino.value}
        )
        assert response.status_code == 409
        assert "nota de credito" in response.json()["detail"]


def test_no_se_salta_la_revision_para_marcar_pagada(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, PENDING)

    response = client.patch(
        f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "paid"}
    )

    assert response.status_code == 409


# --- Publicar exige factura completa --------------------------------------


def test_no_se_publica_sin_importe(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, PENDING, amount=None)

    response = client.patch(
        f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "sent"}
    )

    assert response.status_code == 422
    assert "importe" in response.json()["detail"]


def test_no_se_publica_sin_fecha_de_emision(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, PENDING, issue=None)

    response = client.patch(
        f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "sent"}
    )

    assert response.status_code == 422
    assert "emision" in response.json()["detail"]


def test_no_se_publica_sin_familia(client, db_session):
    staff = _staff(db_session)
    invoice = _invoice(db_session, None, PENDING)

    response = client.patch(
        f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "sent"}
    )

    assert response.status_code == 422
    assert "familia" in response.json()["detail"]


def test_no_se_publica_con_importe_negativo(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, PENDING)

    response = client.patch(
        f"/family-invoices/{invoice.id}",
        headers=_auth(staff),
        json={"status": "sent", "amount": "-500.00"},
    )

    assert response.status_code == 422


def test_el_vencimiento_no_puede_preceder_a_la_emision(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, PENDING)

    response = client.patch(
        f"/family-invoices/{invoice.id}",
        headers=_auth(staff),
        json={"status": "sent", "due_date": "2020-01-01"},
    )

    assert response.status_code == 422


def test_se_publica_una_factura_completa(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, PENDING)

    response = client.patch(
        f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "sent"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    # El vencimiento a 30 dias sigue poniendose solo al publicar (TASK-0053).
    assert response.json()["due_date"] is not None


# --- El lote hereda las mismas reglas -------------------------------------


def test_el_lote_no_descobra_facturas(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    pagadas = [_invoice(db_session, family, PAID) for _ in range(3)]

    response = client.post(
        "/family-invoices/bulk",
        headers=_auth(staff),
        json={"ids": [str(i.id) for i in pagadas], "status": "pending_review"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["updated"] == 0
    assert len(body["failed"]) == 3


def test_el_lote_no_cuenta_dos_veces_la_misma_factura(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, PENDING)

    response = client.post(
        "/family-invoices/bulk",
        headers=_auth(staff),
        json={"ids": [str(invoice.id)] * 3, "status": "sent"},
    )

    assert response.status_code == 200
    assert response.json()["updated"] == 1


# --- La tabla de transiciones, sin pasar por HTTP --------------------------


def test_la_tabla_cubre_los_cuatro_estados():
    assert set(ALLOWED_TRANSITIONS) == {PENDING, SENT, PAID, OVERDUE}


def test_quedarse_en_el_mismo_estado_siempre_se_permite():
    for estado in ALLOWED_TRANSITIONS:
        ensure_transition_allowed(estado, estado)


def test_la_guardia_explica_el_motivo():
    with pytest.raises(InvoiceStateError) as exc:
        ensure_transition_allowed(PAID, PENDING)
    assert exc.value.conflict is True
