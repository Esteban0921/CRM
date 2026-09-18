"""Regresiones de la auditoria 2026-09-18 (TASK-0088, 0091, 0092, 0093, 0094).

Cada test de aqui falla contra el codigo anterior a su arreglo: son las cuatro
formas concretas en que el sistema se dejaba abrir, no comprobaciones genericas.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from config import DEV_JWT_SECRET, Settings, settings
from models.audit_log import AuditedEntityType, AuditLog
from models.document import Document, DocumentType
from models.email import Email
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.note import Note, NoteEntityType
from models.student import Student
from models.user import User, UserRole
from security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, role=user.role.value, family_id=user.family_id)
    return {"Authorization": f"Bearer {token}"}


def _staff(db_session, email="staff-sec@example.com") -> User:
    staff = User(
        email=email,
        password_hash=hash_password("staff1234"),
        name="Staff",
        role=UserRole.STAFF,
    )
    db_session.add(staff)
    db_session.commit()
    return staff


# --- TASK-0088: JWT -------------------------------------------------------


def test_token_sin_exp_es_rechazado(client, db_session):
    """PyJWT no exige `exp` por defecto: sin `require`, un token forjado sin
    caducidad da una sesion eterna.
    """
    staff = _staff(db_session)
    forged = jwt.encode(
        {"sub": str(staff.id), "role": "staff", "iat": datetime.now(UTC)},
        settings.jwt_secret,
        algorithm="HS256",
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


def test_token_con_vigencia_desmedida_es_rechazado(client, db_session):
    """Un `exp` en el ano 2100 pasa la verificacion normal de caducidad."""
    staff = _staff(db_session, email="staff-sec2@example.com")
    now = datetime.now(UTC)
    forged = jwt.encode(
        {
            "sub": str(staff.id),
            "role": "staff",
            "iat": now,
            "exp": now + timedelta(days=3650),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


def test_produccion_no_arranca_con_el_secreto_de_desarrollo():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(app_env="production", jwt_secret=DEV_JWT_SECRET)


def test_produccion_no_arranca_con_un_secreto_corto():
    with pytest.raises(ValueError, match="32 caracteres"):
        Settings(app_env="production", jwt_secret="corto")


def test_produccion_arranca_con_un_secreto_valido():
    config = Settings(app_env="production", jwt_secret="x" * 48)
    assert config.is_production


# --- TASK-0091: descarga de documentos ------------------------------------


def _document(db_session, storage, *, name, body, gmail_id) -> Document:
    path = storage / name
    path.write_bytes(body)
    email = Email(gmail_id=gmail_id)
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id,
        document_type=DocumentType.FAMILY_INVOICE,
        file_path=str(path),
        original_filename=name,
        mime_type="application/pdf",
    )
    db_session.add(document)
    db_session.commit()
    return document


def test_documento_sin_fichero_no_sirve_el_de_otro_con_el_mismo_nombre(
    client, db_session, attachments_dir
):
    """El fallback por nombre base permitia que, al faltar el fichero propio,
    la API devolviera los bytes de otro documento: autorizacion correcta,
    contenido de otra familia (RULE-005).
    """
    victima = _document(
        db_session,
        attachments_dir,
        name="factura.pdf",
        body=b"SECRETO DE OTRA FAMILIA",
        gmail_id="victima",
    )
    atacante = _document(
        db_session,
        attachments_dir,
        name="atacante.pdf",
        body=b"inocuo",
        gmail_id="atacante",
    )
    # El atacante declara el mismo nombre original que la victima y su propio
    # fichero desaparece (cuarentena del antivirus, limpieza de disco).
    atacante.original_filename = "factura.pdf"
    db_session.commit()
    (attachments_dir / "atacante.pdf").unlink()

    staff = _staff(db_session)
    response = client.get(f"/documents/{atacante.id}/file", headers=_auth_header(staff))

    assert response.status_code == 404
    assert b"SECRETO" not in response.content
    # La victima sigue siendo descargable por su propio id.
    ok = client.get(f"/documents/{victima.id}/file", headers=_auth_header(staff))
    assert ok.status_code == 200


def test_documento_fuera_del_almacen_no_se_sirve(client, db_session, attachments_dir, tmp_path):
    # `attachments_dir` es tmp_path/attachments, asi que tmp_path queda fuera.
    afuera = tmp_path / "secreto.pdf"
    afuera.write_bytes(b"fuera del almacen")
    email = Email(gmail_id="fuera-1")
    db_session.add(email)
    db_session.commit()
    document = Document(
        email_id=email.id,
        document_type=DocumentType.FAMILY_INVOICE,
        file_path=str(afuera),
        original_filename="secreto.pdf",
        mime_type="application/pdf",
    )
    db_session.add(document)
    db_session.commit()

    staff = _staff(db_session)
    response = client.get(f"/documents/{document.id}/file", headers=_auth_header(staff))

    assert response.status_code == 404


# --- TASK-0092: anonimizacion RGPD ----------------------------------------


def test_anonimizar_no_deja_los_datos_del_menor_en_el_historial(client, db_session):
    """El endpoint se documenta como derecho de supresion. Antes copiaba
    nombre, fecha de nacimiento y colegio a `audit_logs` y `/activity` los
    seguia sirviendo.
    """
    staff = _staff(db_session)
    family = Family(name="Familia Secreta", address="Calle Secreta 42")
    db_session.add(family)
    db_session.commit()
    student = Student(
        family_id=family.id,
        name="Menor Secreto Auditoria",
        birth_date=datetime(2015, 3, 4).date(),
        school="Colegio Confidencial",
    )
    db_session.add(student)
    db_session.commit()
    db_session.add(
        Note(
            entity_type=NoteEntityType.FAMILY,
            entity_id=family.id,
            body="NOTA INTERNA CONFIDENCIAL",
            created_by=staff.id,
        )
    )
    # Correccion previa: el historial ya contenia PII antes de anonimizar.
    db_session.add(
        AuditLog(
            entity_type=AuditedEntityType.STUDENT,
            entity_id=student.id,
            field_name="name",
            old_value="Menor Secreto Auditoria",
            new_value="Menor Secreto Auditoria II",
            edited_by=staff.id,
        )
    )
    db_session.commit()

    assert (
        client.post(f"/families/{family.id}/anonymize", headers=_auth_header(staff)).status_code
        == 204
    )

    activity = client.get(f"/families/{family.id}/activity", headers=_auth_header(staff))
    assert activity.status_code == 200
    serialized = activity.text
    for leak in (
        "Menor Secreto Auditoria",
        "Colegio Confidencial",
        "2015-03-04",
        "Calle Secreta 42",
        "Familia Secreta",
        "NOTA INTERNA CONFIDENCIAL",
    ):
        assert leak not in serialized, f"{leak} sigue accesible tras anonimizar"


# --- TASK-0093: PII en los logs -------------------------------------------


def test_fk_inexistente_da_409_y_no_500(client, db_session):
    """Un 500 arrastra la sentencia y los parametros al log, con el nombre y la
    fecha de nacimiento del menor dentro (RULE-015).
    """
    staff = _staff(db_session)

    response = client.post(
        "/students",
        headers=_auth_header(staff),
        json={
            "family_id": str(uuid.uuid4()),
            "name": "Lucia Fernandez Menor",
            "birth_date": "2016-05-11",
            "school": "Colegio Santa Ana",
        },
    )

    assert response.status_code in (404, 409, 422)
    assert response.status_code != 500
    assert "Lucia Fernandez Menor" not in response.text


# --- TASK-0094: fuerza bruta y enumeracion --------------------------------


def test_login_se_bloquea_tras_demasiados_intentos(client, db_session):
    staff = _staff(db_session, email="bruta@example.com")
    _ = staff

    codes = []
    for _ in range(settings.login_max_attempts + 2):
        response = client.post(
            "/auth/login", json={"email": "bruta@example.com", "password": "mala"}
        )
        codes.append(response.status_code)

    assert 429 in codes, f"nunca se bloqueo: {codes}"
    # Ni siquiera con la contrasena correcta mientras dure el bloqueo.
    bloqueado = client.post(
        "/auth/login", json={"email": "bruta@example.com", "password": "staff1234"}
    )
    assert bloqueado.status_code == 429


def test_login_correcto_limpia_el_contador(client, db_session):
    _staff(db_session, email="limpia@example.com")

    client.post("/auth/login", json={"email": "limpia@example.com", "password": "mala"})
    ok = client.post("/auth/login", json={"email": "limpia@example.com", "password": "staff1234"})

    assert ok.status_code == 200


def test_el_mensaje_no_distingue_usuario_existente_de_inexistente(client, db_session):
    _staff(db_session, email="existe@example.com")

    existente = client.post("/auth/login", json={"email": "existe@example.com", "password": "mala"})
    inexistente = client.post(
        "/auth/login", json={"email": "no-existe@example.com", "password": "mala"}
    )

    assert existente.status_code == inexistente.status_code == 401
    assert existente.json()["detail"] == inexistente.json()["detail"]


# --- TASK-0098: cabeceras de seguridad ------------------------------------


def test_las_respuestas_llevan_cabeceras_de_seguridad(client):
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_los_datos_de_familia_no_se_cachean(client, db_session):
    staff = _staff(db_session)
    family = Family(name="Familia Cache")
    db_session.add(family)
    db_session.commit()
    invoice_free = client.get(f"/families/{family.id}", headers=_auth_header(staff))

    assert invoice_free.headers.get("Cache-Control") == "no-store"


def test_el_padre_sigue_sin_ver_una_factura_pendiente(client, db_session, attachments_dir):
    """Comprobacion de que el endurecimiento no rompio RULE-017."""
    family = Family(name="Familia RULE017")
    db_session.add(family)
    db_session.commit()
    document = _document(
        db_session, attachments_dir, name="p.pdf", body=b"%PDF", gmail_id="rule017"
    )
    invoice = FamilyInvoice(
        document_id=document.id,
        family_id=family.id,
        status=FamilyInvoiceStatus.PENDING_REVIEW,
    )
    db_session.add(invoice)
    parent = User(
        family_id=family.id,
        email="padre-rule017@example.com",
        password_hash=hash_password("x"),
        name="Padre",
        role=UserRole.PARENT,
    )
    db_session.add(parent)
    db_session.commit()

    assert (
        client.get(f"/family-invoices/{invoice.id}", headers=_auth_header(parent)).status_code
        == 404
    )
    assert (
        client.get(f"/documents/{document.id}/file", headers=_auth_header(parent)).status_code
        == 404
    )
