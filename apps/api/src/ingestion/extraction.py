from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from config import settings


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
    # (?=[A-Z0-9\-/]{0,19}\d): exige al menos un dígito en lo capturado. Sin
    # esto, re.IGNORECASE hace que [A-Z] tambien case con minúsculas y el propio
    # texto de la etiqueta ("Factura", "Nif"...) se cuela como si fuera el valor
    # cuando la etiqueta y el valor no están en la misma línea.
    #
    # Los separadores van con repetición ACOTADA ({0,10}) y el lookahead con
    # longitud máxima. Con `\s*` seguido de `[:\s]*` -dos cuantificadores
    # adyacentes sobre clases que se solapan- el motor parte los espacios en
    # O(n) formas y relanza el lookahead sobre toda la tirada alfanumérica en
    # cada una: un adjunto de 400 KB congelaba el proceso entero 70 segundos,
    # y `re` no suelta el GIL, así que se paraba toda la API (TASK-0090,
    # RULE-016).
    "invoice_number": (
        r"(?:factura|invoice)[\s]{0,10}(?:n[ºo°]?|number)?[:\s]{0,10}"
        r"((?=[A-Z0-9\-/]{0,19}\d)[A-Z0-9\-/]{3,20})"
    ),
    "issue_date": r"(?:fecha|date)[:\s]{0,10}(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    # (?<![a-z]) con IGNORECASE rechaza cualquier letra delante, que es lo que
    # separa «Total» de «Subtotal»: `re.search` encontraba «total» DENTRO de
    # «Subtotal» y la factura entraba por la base imponible, sin IVA
    # (TASK-0115). El lookahead descarta «Total IVA», y el llamador se queda
    # con la ÚLTIMA coincidencia, que es donde las facturas ponen el total.
    "total_amount": (
        r"(?<![a-z])total(?![a-z])(?![^\d\r\n]{0,10}(?:iva|impuest|vat|base))"
        r"[^\d\r\n]{0,20}([\d.,]{1,20})"
    ),
    "tax_id": r"(?:nif|cif|nie)[:\s]{0,10}((?=[A-Z0-9]{0,8}\d)[A-Z0-9]{8,9})",
}

# Campos cuyo valor bueno es la última coincidencia del documento, no la primera.
_LAST_MATCH_FIELDS = {"total_amount"}

_FIELD_COUNT = len(_GENERIC_PATTERNS)


def extract_fields(text: str, templates: list[ExtractionTemplate] | None = None) -> ExtractedFields:
    """Techo de texto antes de tocar un regex (RULE-016: ningún parser corre sin
    límite de recursos). Una factura real no ocupa 256 KB de texto; lo que pasa
    de ahí es un adjunto hostil o un PDF roto, y en ninguno de los dos casos
    merece gastar el proceso entero.
    """
    text = text[: settings.max_extraction_text_bytes]

    for template in templates or []:
        if template.matches(text):
            return _apply_patterns(text, template.patterns, base_confidence=0.85)

    return _apply_patterns(text, _GENERIC_PATTERNS, base_confidence=0.4)


def _apply_patterns(text: str, patterns: dict[str, str], base_confidence: float) -> ExtractedFields:
    found: dict[str, str] = {}
    for field_name, pattern in patterns.items():
        if field_name in _LAST_MATCH_FIELDS:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            match = matches[-1] if matches else None
        else:
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
    """Interpreta importes de facturas ES: `45,00`, `1.234,56`, `45.00`, `1.234`.

    El caso sin coma era el roto: `1.234` (miles en formato español, sin
    decimales) se interpretaba como `Decimal("1.234")` y `Numeric(10, 2)` lo
    redondeaba a `1,23 €`. Error de factor 1000 a la baja, silencioso
    (TASK-0116).
    """
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
    elif "." in cleaned and _dot_is_thousands_separator(cleaned):
        cleaned = cleaned.replace(".", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _dot_is_thousands_separator(cleaned: str) -> bool:
    """Sin coma en el importe, el punto es ambiguo: `45.00` son decimales y
    `1.234` son miles. Un grupo final de EXACTAMENTE tres dígitos solo aparece
    en el separador de miles: un importe en euros no tiene tres decimales.
    """
    if "." not in cleaned:
        return False
    head, _, tail = cleaned.rpartition(".")
    if not head or not head.replace(".", "").isdigit() or not tail.isdigit():
        return False
    return len(tail) == 3


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
