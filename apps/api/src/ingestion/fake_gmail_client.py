from __future__ import annotations

from ingestion.gmail_client import RawEmail

_TERMINAL_LABELS = {"AUTO/PROCESSED", "AUTO/FAILED", "AUTO/IGNORED"}


class FakeGmailClient:
    """Simula un buzón de Gmail en memoria: credenciales de Gmail simuladas
    (decisión 2026-08-25 del usuario) en vez de esperar a las reales.
    Implementa el mismo protocolo que `GmailClient`.

    "Nuevo" se decide por etiqueta, igual que en Gmail real (filtrar por
    labelIds sin AUTO/PROCESSED ni similares) — no por si ya se llamó a
    get_message(), que solo simula la lectura del mensaje.
    """

    def __init__(self, inbox: list[RawEmail] | None = None):
        self._inbox = {email.gmail_id: email for email in (inbox or [])}
        self._labels: dict[str, list[str]] = {}

    def list_new_message_ids(self) -> list[str]:
        return [
            gid
            for gid in self._inbox
            if not _TERMINAL_LABELS.intersection(self._labels.get(gid, []))
        ]

    def get_message(self, message_id: str) -> RawEmail:
        return self._inbox[message_id]

    def apply_label(self, message_id: str, label: str) -> None:
        self._labels.setdefault(message_id, []).append(label)

    def labels_for(self, message_id: str) -> list[str]:
        return self._labels.get(message_id, [])
