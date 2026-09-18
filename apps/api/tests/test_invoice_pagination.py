"""Paginacion del listado de facturas (TASK-0126, TASK-0113).

Antes devolvia la tabla entera: con 2.064 facturas, 315 ms y 1,23 MB por
peticion, perfectamente lineal. El cuello no era Postgres -0,39 ms de
ejecucion- sino cargar todas las filas en el proceso y pasarlas por Pydantic.
"""

import datetime
import uuid
from decimal import Decimal

from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.user import User, UserRole
from routers.family_invoices import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, TOTAL_HEADER
from security import create_access_token, hash_password


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


def _seed(db_session, family, count, status=FamilyInvoiceStatus.PENDING_REVIEW):
    email = Email(gmail_id=f"g-{uuid.uuid4()}")
    db_session.add(email)
    db_session.commit()
    for _ in range(count):
        document = Document(
            email_id=email.id, document_type=DocumentType.FAMILY_INVOICE, file_path="f.pdf"
        )
        db_session.add(document)
        db_session.flush()
        db_session.add(
            FamilyInvoice(
                document_id=document.id,
                family_id=family.id,
                status=status,
                amount=Decimal("45.00"),
                issue_date=datetime.date(2026, 9, 1),
            )
        )
    db_session.commit()


def _family(db_session) -> Family:
    family = Family(name=f"Familia {uuid.uuid4().hex[:6]}")
    db_session.add(family)
    db_session.commit()
    return family


def test_el_listado_no_devuelve_mas_del_tamano_de_pagina(client, db_session):
    staff = _staff(db_session)
    _seed(db_session, _family(db_session), DEFAULT_PAGE_SIZE + 20)

    response = client.get("/family-invoices", headers=_auth(staff))

    assert response.status_code == 200
    assert len(response.json()) == DEFAULT_PAGE_SIZE
    assert response.headers[TOTAL_HEADER] == str(DEFAULT_PAGE_SIZE + 20)


def test_el_offset_recorre_el_resto_sin_repetir(client, db_session):
    staff = _staff(db_session)
    _seed(db_session, _family(db_session), 30)

    primera = client.get("/family-invoices?limit=10&offset=0", headers=_auth(staff)).json()
    segunda = client.get("/family-invoices?limit=10&offset=10", headers=_auth(staff)).json()
    tercera = client.get("/family-invoices?limit=10&offset=20", headers=_auth(staff)).json()

    ids = [row["id"] for row in primera + segunda + tercera]
    assert len(ids) == 30
    assert len(set(ids)) == 30, "la paginacion repite o se salta filas"


def test_el_total_es_el_del_servidor_no_el_de_la_pagina(client, db_session):
    staff = _staff(db_session)
    _seed(db_session, _family(db_session), 25)

    response = client.get("/family-invoices?limit=5", headers=_auth(staff))

    assert len(response.json()) == 5
    assert response.headers[TOTAL_HEADER] == "25"


def test_el_total_respeta_el_filtro_de_estado(client, db_session):
    staff = _staff(db_session)
    family = _family(db_session)
    _seed(db_session, family, 7, status=FamilyInvoiceStatus.PENDING_REVIEW)
    _seed(db_session, family, 3, status=FamilyInvoiceStatus.PAID)

    pendientes = client.get("/family-invoices?status=pending_review", headers=_auth(staff))
    pagadas = client.get("/family-invoices?status=paid", headers=_auth(staff))

    assert pendientes.headers[TOTAL_HEADER] == "7"
    assert pagadas.headers[TOTAL_HEADER] == "3"


def test_no_se_puede_pedir_una_pagina_desmedida(client, db_session):
    staff = _staff(db_session)

    assert (
        client.get(f"/family-invoices?limit={MAX_PAGE_SIZE + 1}", headers=_auth(staff)).status_code
        == 422
    )
    assert client.get("/family-invoices?limit=0", headers=_auth(staff)).status_code == 422
    assert client.get("/family-invoices?offset=-1", headers=_auth(staff)).status_code == 422


def test_el_padre_sigue_viendo_solo_lo_suyo_al_paginar(client, db_session):
    """La paginacion se aplica DESPUES del filtrado por familia: un `offset`
    grande no puede asomar a las facturas de otra familia (RULE-005).
    """
    mia = _family(db_session)
    otra = _family(db_session)
    _seed(db_session, mia, 3, status=FamilyInvoiceStatus.SENT)
    _seed(db_session, otra, 20, status=FamilyInvoiceStatus.SENT)
    parent = User(
        family_id=mia.id,
        email=f"padre-{uuid.uuid4()}@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    response = client.get("/family-invoices?limit=100", headers=_auth(parent))

    assert response.headers[TOTAL_HEADER] == "3"
    assert {row["family_id"] for row in response.json()} == {str(mia.id)}
