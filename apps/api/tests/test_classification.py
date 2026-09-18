from ingestion.classification import classify_document
from models.document import DocumentType


def test_pdf_defaults_to_family_invoice():
    result = classify_document(filename="factura.pdf", subject="Tu factura de septiembre")

    assert result == DocumentType.FAMILY_INVOICE


def test_known_supplier_address_is_supplier_invoice():
    result = classify_document(
        filename="factura.pdf",
        from_address="facturas@repsol.com",
        known_supplier_addresses={"facturas@repsol.com"},
    )

    assert result == DocumentType.SUPPLIER_INVOICE


def test_known_supplier_display_name_is_still_supplier_invoice():
    result = classify_document(
        filename="factura.pdf",
        from_address="Repsol Facturacion <facturas@repsol.com>",
        known_supplier_addresses={"facturas@repsol.com"},
    )

    assert result == DocumentType.SUPPLIER_INVOICE


def test_credit_note_keyword_is_detected():
    result = classify_document(filename="documento.pdf", subject="Nota de crédito nº 123")

    assert result == DocumentType.CREDIT_NOTE


def test_newsletter_is_classified_as_noise():
    result = classify_document(filename="boletin.pdf", subject="Newsletter de agosto")

    assert result == DocumentType.OTHER


def test_unsupported_extension_is_unknown():
    result = classify_document(filename="imagen.png", subject="Factura")

    assert result == DocumentType.UNKNOWN
