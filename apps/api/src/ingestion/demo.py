"""Correo de prueba para el botón de ingesta (TASK-0048).

Gmail real sigue en TASK-0032: este fixture alimenta FakeGmailClient con un
PDF-texto que las plantillas genéricas sí extraen (importe y fecha ES).
"""

from __future__ import annotations

import uuid

from ingestion.gmail_client import RawAttachment, RawEmail

DEMO_INVOICE_TEXT = """
FACTURA
Factura Nº: INV-DEMO-001
Fecha: 01/09/2026
NIF: B12345678
Total: 45,00 EUR
Alumno: Ana Garcia Perez
""".encode()


def demo_inbox() -> list[RawEmail]:
    return [
        RawEmail(
            gmail_id=f"demo-{uuid.uuid4()}",
            subject="Factura de transporte (correo de prueba)",
            from_address="admin@crm-transporte.local",
            attachments=[
                RawAttachment(
                    filename="factura.pdf",
                    mime_type="application/pdf",
                    content=DEMO_INVOICE_TEXT,
                )
            ],
        )
    ]
