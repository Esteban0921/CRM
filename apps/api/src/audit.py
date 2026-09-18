import uuid
from typing import Any

from sqlalchemy.orm import Session

from models.audit_log import AuditedEntityType, AuditLog


def record_field_changes(
    db: Session,
    *,
    entity_type: AuditedEntityType,
    entity_id: uuid.UUID,
    editor_id: uuid.UUID,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    """RULE-009/TASK-0026: cualquier PATCH que corrija un campo deja rastro.

    Solo registra los campos que de verdad cambiaron (before != after);
    silencioso si `after` no toca nada de `before`.
    """
    for field_name, new_value in after.items():
        old_value = before.get(field_name)
        if old_value == new_value:
            continue
        db.add(
            AuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
                old_value=None if old_value is None else str(old_value),
                new_value=None if new_value is None else str(new_value),
                edited_by=editor_id,
            )
        )


REDACTED = "[dato suprimido]"


def record_redaction(
    db: Session,
    *,
    entity_type: AuditedEntityType,
    entity_id: uuid.UUID,
    editor_id: uuid.UUID,
    field_names: list[str],
) -> None:
    """Deja constancia de que un campo se suprimio, sin copiar lo suprimido.

    `record_field_changes` guarda `old_value=str(valor_anterior)`, asi que
    anonimizar una familia escribia el nombre, la fecha de nacimiento y el
    colegio del menor en `audit_logs` y `/families/{id}/activity` los seguia
    sirviendo: el derecho de supresion no se ejercia, se documentaba
    (TASK-0092, RULE-015).
    """
    for field_name in field_names:
        db.add(
            AuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
                old_value=REDACTED,
                new_value=REDACTED,
                edited_by=editor_id,
            )
        )


def redact_existing_audit_trail(
    db: Session,
    *,
    entity_type: AuditedEntityType,
    entity_ids: list[uuid.UUID],
) -> int:
    """Pisa los valores de las correcciones YA registradas sobre esas entidades.

    Conserva la fila -que el campo cambio, quien y cuando, que es lo que exige
    la trazabilidad- y borra el contenido, que es lo que exige la supresion.
    """
    if not entity_ids:
        return 0
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == entity_type, AuditLog.entity_id.in_(entity_ids))
        .all()
    )
    for row in rows:
        row.old_value = REDACTED
        row.new_value = REDACTED
    return len(rows)
