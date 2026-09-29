"""Cobros y fecha de cobro (TASK-0157, TASK-0102).

`paid` era solo un valor de `status`. La consecuencia contable, medida por la
auditoria sobre datos reales: `collected_amount` se calculaba filtrando por
`issue_date`, asi que una factura de agosto pagada en septiembre no aparecia en
el cierre de NINGUN mes, y el de agosto cambiaba retroactivamente.
"""

import datetime
import uuid
from decimal import Decimal

from models.audit_log import AuditLog
from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.payment import Payment
from models.user import User, UserRole
from security import create_access_token, hash_password

HOY = datetime.date.today()
MES_INICIO = HOY.replace(day=1)
MES_ANTERIOR = (MES_INICIO - datetime.timedelta(days=1)).replace(day=1)


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


def _family(db_session) -> Family:
    family = Family(name=f"Familia {uuid.uuid4().hex[:6]}")
    db_session.add(family)
    db_session.commit()
    return family


def _invoice(db_session, family, *, amount="100.00", issue_date=None, status=None):
    email = Email(gmail_id=f"pay-{uuid.uuid4()}")
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id, document_type=DocumentType.FAMILY_INVOICE, file_path="f.pdf"
    )
    db_session.add(document)
    db_session.commit()
    invoice = FamilyInvoice(
        document_id=document.id,
        family_id=family.id,
        amount=Decimal(amount),
        issue_date=issue_date or MES_INICIO,
        status=status or FamilyInvoiceStatus.SENT,
    )
    db_session.add(invoice)
    db_session.commit()
    return invoice


# --- El descuadre contable que motivo todo esto ---------------------------


def test_un_cobro_de_este_mes_sobre_una_factura_del_anterior_si_cuenta(client, db_session):
    """El caso exacto de la auditoria: factura emitida el mes pasado, cobrada
    este. Antes no aparecia en el cierre de ningun mes.
    """
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, amount="150.00", issue_date=MES_ANTERIOR)

    respuesta = client.post(
        f"/family-invoices/{invoice.id}/payments",
        headers=_auth(staff),
        json={"amount": "150.00", "paid_on": HOY.isoformat()},
    )
    assert respuesta.status_code == 201, respuesta.text

    resumen = client.get("/billing/summary", headers=_auth(staff)).json()
    assert resumen["collected_amount"] == "150.00", (
        "el cobro de este mes no cuenta en el cierre de este mes"
    )


def test_una_factura_de_este_mes_cobrada_el_mes_pasado_no_infla_este(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, amount="80.00", issue_date=MES_INICIO)

    client.post(
        f"/family-invoices/{invoice.id}/payments",
        headers=_auth(staff),
        json={"amount": "80.00", "paid_on": MES_ANTERIOR.isoformat()},
    )

    resumen = client.get("/billing/summary", headers=_auth(staff)).json()
    assert resumen["collected_amount"] == "0.00"


def test_marcar_pagada_a_mano_deja_un_cobro(client, db_session):
    """El kanban permite mover a `paid` de un tiron. Si eso no generase un
    cobro, el importe desapareceria del cierre del mes.
    """
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, amount="45.00")

    client.patch(f"/family-invoices/{invoice.id}", headers=_auth(staff), json={"status": "paid"})

    pagos = db_session.query(Payment).filter(Payment.invoice_id == invoice.id).all()
    assert len(pagos) == 1
    assert pagos[0].amount == Decimal("45.00")
    db_session.refresh(invoice)
    assert invoice.paid_at == HOY
    assert (
        client.get("/billing/summary", headers=_auth(staff)).json()["collected_amount"] == "45.00"
    )


# --- Pagos parciales -------------------------------------------------------


def test_un_pago_parcial_no_salda_la_factura(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, amount="100.00")

    respuesta = client.post(
        f"/family-invoices/{invoice.id}/payments",
        headers=_auth(staff),
        json={"amount": "40.00"},
    )

    assert respuesta.status_code == 201
    db_session.refresh(invoice)
    assert invoice.status == FamilyInvoiceStatus.SENT, "un pago parcial no cierra la factura"
    assert invoice.paid_at is None
    # La deuda baja a lo que queda: si un pago parcial no cambiara nada de lo
    # que ve el staff, registrarlo seria puro adorno (TASK-0157).
    billing = client.get(f"/families/{family.id}/billing", headers=_auth(staff)).json()
    assert billing["outstanding_amount"] == "60.00"


def test_el_segundo_pago_salda_la_factura(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, amount="100.00")

    client.post(
        f"/family-invoices/{invoice.id}/payments",
        headers=_auth(staff),
        json={"amount": "40.00", "paid_on": MES_INICIO.isoformat()},
    )
    client.post(
        f"/family-invoices/{invoice.id}/payments",
        headers=_auth(staff),
        json={"amount": "60.00", "paid_on": HOY.isoformat()},
    )

    db_session.refresh(invoice)
    assert invoice.status == FamilyInvoiceStatus.PAID
    # Queda saldada el dia del ULTIMO pago, no del primero.
    assert invoice.paid_at == HOY


def test_el_cobro_que_salda_la_factura_deja_rastro_en_el_audit_trail(client, db_session):
    """Pasar a `paid` por PATCH deja rastro; saldarla con un cobro tambien
    tiene que dejarlo. Si no, el historial de la factura no explica por que
    cambio de estado ni quien lo hizo.
    """
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, amount="100.00")

    client.post(
        f"/family-invoices/{invoice.id}/payments",
        headers=_auth(staff),
        json={"amount": "40.00"},
    )
    parcial = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_id == invoice.id, AuditLog.field_name == "status")
        .count()
    )
    assert parcial == 0, "un pago parcial no cambia el estado"

    client.post(
        f"/family-invoices/{invoice.id}/payments",
        headers=_auth(staff),
        json={"amount": "60.00", "paid_on": HOY.isoformat()},
    )

    rastro = {
        entrada.field_name: entrada
        for entrada in db_session.query(AuditLog).filter(AuditLog.entity_id == invoice.id).all()
    }
    assert rastro["status"].old_value == "sent"
    assert rastro["status"].new_value == "paid"
    assert rastro["status"].edited_by == staff.id
    assert rastro["paid_at"].new_value == HOY.isoformat()


def test_no_se_puede_cobrar_mas_de_lo_que_queda(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, amount="50.00")
    client.post(
        f"/family-invoices/{invoice.id}/payments", headers=_auth(staff), json={"amount": "30.00"}
    )

    respuesta = client.post(
        f"/family-invoices/{invoice.id}/payments", headers=_auth(staff), json={"amount": "40.00"}
    )

    assert respuesta.status_code == 422
    assert "pendiente" in respuesta.json()["detail"]


def test_un_importe_de_cero_o_negativo_se_rechaza(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family)

    for importe in ("0", "-10.00"):
        respuesta = client.post(
            f"/family-invoices/{invoice.id}/payments",
            headers=_auth(staff),
            json={"amount": importe},
        )
        assert respuesta.status_code == 422


# --- Reglas de negocio y de acceso ----------------------------------------


def test_no_se_cobra_una_factura_en_revision(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, status=FamilyInvoiceStatus.PENDING_REVIEW)

    respuesta = client.post(
        f"/family-invoices/{invoice.id}/payments", headers=_auth(staff), json={"amount": "10.00"}
    )

    assert respuesta.status_code == 422
    assert "Publica" in respuesta.json()["detail"]


def test_no_se_cobra_una_factura_sin_importe(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family)
    invoice.amount = None
    db_session.commit()

    respuesta = client.post(
        f"/family-invoices/{invoice.id}/payments", headers=_auth(staff), json={"amount": "10.00"}
    )

    assert respuesta.status_code == 422


def test_el_padre_no_registra_cobros(client, db_session):
    family = _family(db_session)
    invoice = _invoice(db_session, family)
    parent = User(
        family_id=family.id,
        email=f"padre-{uuid.uuid4()}@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    respuesta = client.post(
        f"/family-invoices/{invoice.id}/payments", headers=_auth(parent), json={"amount": "10.00"}
    )

    assert respuesta.status_code == 403


def test_el_padre_ve_los_cobros_de_su_factura_pero_no_los_de_otra(client, db_session):
    staff = _staff(db_session)
    mia = _family(db_session)
    otra = _family(db_session)
    mi_factura = _invoice(db_session, mia, amount="20.00")
    otra_factura = _invoice(db_session, otra, amount="20.00")
    client.post(
        f"/family-invoices/{mi_factura.id}/payments", headers=_auth(staff), json={"amount": "20.00"}
    )
    client.post(
        f"/family-invoices/{otra_factura.id}/payments",
        headers=_auth(staff),
        json={"amount": "20.00"},
    )
    parent = User(
        family_id=mia.id,
        email=f"padre-{uuid.uuid4()}@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    mios = client.get(f"/family-invoices/{mi_factura.id}/payments", headers=_auth(parent))
    ajenos = client.get(f"/family-invoices/{otra_factura.id}/payments", headers=_auth(parent))

    assert mios.status_code == 200
    assert len(mios.json()) == 1
    assert ajenos.status_code == 404, "RULE-005: no puede leer los cobros de otra familia"


def test_el_padre_no_ve_los_cobros_de_una_factura_en_revision(client, db_session):
    family = _family(db_session)
    invoice = _invoice(db_session, family, status=FamilyInvoiceStatus.PENDING_REVIEW)
    parent = User(
        family_id=family.id,
        email=f"padre-{uuid.uuid4()}@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    respuesta = client.get(f"/family-invoices/{invoice.id}/payments", headers=_auth(parent))

    assert respuesta.status_code == 404


def test_confirmar_cobro_sigue_funcionando_y_deja_el_pago(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    invoice = _invoice(db_session, family, amount="33.00")

    respuesta = client.post(f"/family-invoices/{invoice.id}/confirm-payment", headers=_auth(staff))

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "paid"
    assert db_session.query(Payment).filter(Payment.invoice_id == invoice.id).count() == 1
