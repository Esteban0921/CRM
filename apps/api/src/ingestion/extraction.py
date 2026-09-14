from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass
class ExtractedFields:
    invoice_number: str | None = None
    issue_date: str | None = None
    total_amount: str | None = None
    tax_id: str | None = None
    confidence: float = 0.0


@dataclass
class ExtractionTemplate:
    """Inspirado en el patrón de plantillas de invoice2data (ver auditoría
    comparativa en ISSUES.md): un proveedor conocido -> sus propios regex por
    campo, más fiables que el genérico. Sin plantilla que reconozca el texto
    se usa el patrón genérico, con menor confianza.
    """

    name: str
    keywords: list[str]
    patterns: dict[str, str]

    def matches(self, text: str) -> bool:
        lowered = text.lower()
        return all(keyword.lower() in lowered for keyword in self.keywords)


_GENERIC_PATTERNS = {
    # (?=[A-Z0-9\-/]*\d): exige al menos un dígito en lo capturado. Sin esto,
    # re.IGNORECASE hace que [A-Z] tambien case con minúsculas y el propio
    # texto de la etiqueta ("Factura", "Nif"...) se cuela como si fuera el
    # valor cuando la etiqueta y el valor no están en la misma línea.
    "invoice_number": (
        r"(?:factura|invoice)\s*(?:n[ºo°]?|number)?[:\s]*((?=[A-Z0-9\-/]*\d)[A-Z0-9\-/]{3,20})"
    ),
    "issue_date": r"(?:fecha|date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    "total_amount": r"total[:\s]*([\d.,]+)\s*(?:€|eur)?",
    "tax_id": r"(?:nif|cif|nie)[:\s]*((?=[A-Z0-9]*\d)[A-Z0-9]{8,9})",
}

_FIELD_COUNT = len(_GENERIC_PATTERNS)


def extract_fields(text: str, templates: list[ExtractionTemplate] | None = None) -> ExtractedFields:
    for template in templates or []:
        if template.matches(text):
            return _apply_patterns(text, template.patterns, base_confidence=0.85)

    return _apply_patterns(text, _GENERIC_PATTERNS, base_confidence=0.4)


def _apply_patterns(text: str, patterns: dict[str, str], base_confidence: float) -> ExtractedFields:
    found: dict[str, str] = {}
    for field_name, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            found[field_name] = match.group(1).strip()

    confidence = base_confidence * (len(found) / _FIELD_COUNT) if _FIELD_COUNT else 0.0

    return ExtractedFields(
        invoice_number=found.get("invoice_number"),
        issue_date=found.get("issue_date"),
        total_amount=found.get("total_amount"),
        tax_id=found.get("tax_id"),
        confidence=round(confidence, 2),
    )


def parse_spanish_amount(raw: str | None) -> Decimal | None:
    """Interpreta importes de facturas ES: `45,00`, `1.234,56`, `45.00`."""
    if raw is None:
        return None
    cleaned = (
        raw.strip()
        .replace("€", "")
        .replace("EUR", "")
        .replace("eur", "")
        .replace("\xa0", "")
        .replace(" ", "")
    )
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_spanish_date(raw: str | None) -> datetime.date | None:
    """Acepta dd/mm/yyyy, dd-mm-yyyy, dd/mm/yy e ISO yyyy-mm-dd."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
