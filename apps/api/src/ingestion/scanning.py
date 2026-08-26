from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class ScanResult:
    clean: bool
    detail: str = ""


class AttachmentScanner(Protocol):
    def scan(self, file_path: str | Path) -> ScanResult: ...


class NoOpScanner:
    """No escanea nada de verdad. Solo para desarrollo/tests.

    RULE-016: en cualquier entorno real hay que sustituirlo por
    `ClamdScanner` con un daemon `clamd` real corriendo (TASK-0033/Docker).
    """

    def scan(self, file_path: str | Path) -> ScanResult:
        return ScanResult(clean=True, detail="NoOpScanner: sin escaneo real, solo dev/tests")


class ClamdScanner:
    """Requiere `pip install clamd` y un daemon clamd real (servicio `clamav`
    en docker-compose.yml). Verificado en TASK-0033 contra archivo limpio y
    contra el string de prueba EICAR.
    """

    def __init__(self, host: str = "localhost", port: int = 3310, timeout: float = 10.0):
        self._host = host
        self._port = port
        self._timeout = timeout

    def scan(self, file_path: str | Path) -> ScanResult:
        import clamd

        client = clamd.ClamdNetworkSocket(host=self._host, port=self._port, timeout=self._timeout)
        with open(file_path, "rb") as handle:
            result = client.instream(handle)
        status, detail = result["stream"]
        return ScanResult(clean=status == "OK", detail=detail or status)
