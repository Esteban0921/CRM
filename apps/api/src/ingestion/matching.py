from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy.orm import Session

from models.student import Student, StudentStatus

# Un match de una sola palabra corta es ruido: "Ana", "Luz" o "Sol" aparecen
# dentro de cualquier texto comercial. Se exige o bien varias palabras, o bien
# una palabra suficientemente larga.
MIN_SINGLE_WORD_LENGTH = 6


def normalize(text: str) -> str:
    """Minusculas y sin acentos, para comparar nombres.

    Sin esto, `JOSE NUNEZ` escrito con acentos en el PDF no emparejaba con el
    alumno `Jose Nunez` de la base de datos, y el fallo era silencioso: la
    factura se quedaba sin familia (TASK-0117).
    """
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.casefold()


def _is_discriminating(name: str) -> bool:
    words = [word for word in name.split() if word]
    if len(words) >= 2:
        return True
    return bool(words) and len(words[0]) >= MIN_SINGLE_WORD_LENGTH


def name_appears_in(name: str, text: str) -> bool:
    """Busca el nombre como palabras completas, no como subcadena.

    `"ana" in "servicio de la semana"` era cierto, y por ahi una factura sin
    ningun nombre de alumno se enlazo a la familia del alumno "Ana": el guard
    de RULE-005 no falla, pero el `family_id` ya viene mal desde la ingesta,
    que es la forma mas realista de que un padre acabe viendo la factura de
    otra familia (TASK-0117).
    """
    normalized_name = normalize(name).strip()
    if not normalized_name or not _is_discriminating(normalized_name):
        return False
    pattern = r"\b" + r"\s+".join(re.escape(word) for word in normalized_name.split()) + r"\b"
    return re.search(pattern, normalize(text)) is not None


def match_student_by_name_in_text(
    db: Session, text: str
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Busca el nombre de un alumno activo dentro del texto de una factura
    (TASK-0030). Devuelve (family_id, student_id) si hay exactamente una
    coincidencia; (None, None) si no hay ninguna o hay más de una — ambiguo,
    queda para revisión manual (staff) en vez de arriesgar un enlace erróneo.
    """
    students = db.query(Student).filter(Student.status == StudentStatus.ACTIVE).all()
    matches = [s for s in students if s.name and name_appears_in(s.name, text)]

    if len(matches) == 1:
        return matches[0].family_id, matches[0].id
    return None, None
