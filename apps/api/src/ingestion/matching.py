from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from models.student import Student, StudentStatus


def match_student_by_name_in_text(
    db: Session, text: str
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Busca el nombre de un alumno activo dentro del texto de una factura
    (TASK-0030). Devuelve (family_id, student_id) si hay exactamente una
    coincidencia; (None, None) si no hay ninguna o hay más de una — ambiguo,
    queda para revisión manual (staff) en vez de arriesgar un enlace erróneo.
    """
    lowered_text = text.lower()
    students = db.query(Student).filter(Student.status == StudentStatus.ACTIVE).all()
    matches = [s for s in students if s.name and s.name.lower() in lowered_text]

    if len(matches) == 1:
        return matches[0].family_id, matches[0].id
    return None, None
