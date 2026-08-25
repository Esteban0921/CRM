from __future__ import annotations

import re
from dataclasses import dataclass


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
