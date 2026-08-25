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
