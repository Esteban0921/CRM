from __future__ import annotations

import re

from models.document import DocumentType

_CREDIT_NOTE_KEYWORDS = re.compile(r"nota de cr[eé]dito|credit note|\babono\b", re.IGNORECASE)
_NOISE_KEYWORDS = re.compile(
    r"newsletter|invitaci[oó]n|webinar|\bforo\b|bolet[ií]n|unsubscribe", re.IGNORECASE
)
_INVOICE_EXTENSIONS = {"pdf", "xml"}


def classify_document(
    *,
    filename: str,
    subject: str | None = None,
    from_address: str | None = None,
    known_supplier_addresses: set[str] | None = None,
) -> DocumentType:
    """Reglas deterministas primero (spec original sección 4). Sin ML/LLM:
    esa decisión sigue abierta (sección 12 de SPEC_ORIGINAL.md).
    """
    text = f"{filename} {subject or ''}"

    if _NOISE_KEYWORDS.search(text):
        return DocumentType.OTHER

    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension not in _INVOICE_EXTENSIONS:
        return DocumentType.UNKNOWN

    if _CREDIT_NOTE_KEYWORDS.search(text):
        return DocumentType.CREDIT_NOTE

    if (
        from_address
        and known_supplier_addresses
        and from_address.lower() in known_supplier_addresses
    ):
        return DocumentType.SUPPLIER_INVOICE

    return DocumentType.FAMILY_INVOICE
