import datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from models.audit_log import AuditedEntityType, AuditLog
from models.document import Document, DocumentType
from models.email import Email, EmailProcessingStatus
from models.family import Family
from models.family_invoice import FamilyInvoice, FamilyInvoiceStatus
from models.supplier import Supplier, SupplierCategory
from models.supplier_invoice import SupplierInvoice
from models.user import User, UserRole


def test_email_round_trips_with_labels_and_default_status(db_session):
    email = Email(gmail_id="gmail-1", subject="Factura", labels=["AUTO/PENDING"])

    db_session.add(email)
    db_session.commit()

    stored = db_session.get(Email, email.id)
    assert stored.processing_status == EmailProcessingStatus.PENDING
    assert stored.labels == ["AUTO/PENDING"]


def test_duplicate_gmail_id_is_rejected(db_session):
    db_session.add(Email(gmail_id="dup"))
    db_session.commit()

    db_session.add(Email(gmail_id="dup"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_document_zip_member_references_parent(db_session):
    email = Email(gmail_id="gmail-2")
    db_session.add(email)
    db_session.commit()

    zip_doc = Document(
        email_id=email.id,
        document_type=DocumentType.UNKNOWN,
        file_path="2026/09/factura.zip",
        is_zip_member=False,
    )
    db_session.add(zip_doc)
    db_session.commit()

    member = Document(
        email_id=email.id,
        document_type=DocumentType.FAMILY_INVOICE,
        file_path="2026/09/factura.pdf",
        is_zip_member=True,
        parent_zip_id=zip_doc.id,
    )
    db_session.add(member)
    db_session.commit()

    stored = db_session.get(Document, member.id)
    assert stored.parent_zip_id == zip_doc.id
    assert stored.email.gmail_id == "gmail-2"


def test_family_invoice_links_document_and_family(db_session):
    family = Family(name="Familia Invoice")
    email = Email(gmail_id="gmail-3")
    db_session.add_all([family, email])
    db_session.commit()

    document = Document(
        email_id=email.id, document_type=DocumentType.FAMILY_INVOICE, file_path="f.pdf"
    )
    db_session.add(document)
    db_session.commit()

    invoice = FamilyInvoice(
        document_id=document.id,
        family_id=family.id,
        amount=Decimal("45.00"),
        issue_date=datetime.date(2026, 9, 1),
        confidence=0.92,
    )
    db_session.add(invoice)
    db_session.commit()

    stored = db_session.get(FamilyInvoice, invoice.id)
    assert stored.status == FamilyInvoiceStatus.PENDING_REVIEW
    assert stored.currency == "EUR"
    assert stored.confidence == pytest.approx(0.92)


def test_supplier_invoice_links_document_and_supplier(db_session):
    supplier = Supplier(name="Repsol", category=SupplierCategory.FUEL)
    email = Email(gmail_id="gmail-4")
    db_session.add_all([supplier, email])
    db_session.commit()

    document = Document(
        email_id=email.id, document_type=DocumentType.SUPPLIER_INVOICE, file_path="g.pdf"
    )
    db_session.add(document)
    db_session.commit()

    invoice = SupplierInvoice(
        document_id=document.id,
        supplier_id=supplier.id,
        category=SupplierCategory.FUEL,
        amount=Decimal("120.50"),
    )
    db_session.add(invoice)
    db_session.commit()

    stored = db_session.get(SupplierInvoice, invoice.id)
    assert stored.supplier_id == supplier.id
    assert stored.category == SupplierCategory.FUEL


def test_audit_log_records_manual_correction(db_session):
    staff = User(email="staff@example.com", password_hash="x", name="Staff", role=UserRole.STAFF)
    db_session.add(staff)
    db_session.commit()

    entry = AuditLog(
        entity_type=AuditedEntityType.FAMILY_INVOICE,
        entity_id=staff.id,  # cualquier UUID sirve para el test, no es FK real
        field_name="amount",
        old_value="40.00",
        new_value="45.00",
        edited_by=staff.id,
    )
    db_session.add(entry)
    db_session.commit()

    stored = db_session.get(AuditLog, entry.id)
    assert stored.field_name == "amount"
    assert stored.edited_by == staff.id
