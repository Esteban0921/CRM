from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class ScanResult:
    clean: bool
    detail: str = ""


class ScannerUnavailableError(RuntimeError):
    """El antivirus no puede dar un veredicto: se falla cerrado (RULE-016)."""


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
        # `instream` devuelve None mientras clamd esta arrancando y cargando
        # firmas: sin esta comprobacion el `result["stream"]` lanzaba un
        # TypeError opaco que quemaba el lote entero de correos con
        # "'NoneType' object is not subscriptable" (TASK-0120).
        if not isinstance(result, dict) or "stream" not in result:
            raise ScannerUnavailableError(
                "El antivirus respondio sin veredicto (probablemente aun esta "
                "cargando las firmas). No se escanea a medias (RULE-016)."
            )
        status, detail = result["stream"]
        return ScanResult(clean=status == "OK", detail=detail or status)


def build_attachment_scanner() -> AttachmentScanner:
    """Escaner real, o error claro si el daemon no esta listo (RULE-016).

    `ping()` responde en cuanto existe el socket, pero clamd tarda minutos en
    cargar las firmas (`start_period: 300s` en docker-compose.yml). En esa
    ventana la instancia esta viva y es inutil, asi que se comprueba tambien
    que responda una version (TASK-0120).
    """
    import clamd

    from config import settings

    try:
        client = clamd.ClamdNetworkSocket(
            host=settings.clamav_host, port=settings.clamav_port, timeout=3.0
        )
        client.ping()
        client.version()
    except Exception as exc:
        raise ScannerUnavailableError(
            "Antivirus (clamd) no disponible: no se puede escanear con seguridad "
            "los adjuntos entrantes (RULE-016). Comprueba el servicio `clamav` "
            "de docker-compose.yml."
        ) from exc
    return ClamdScanner(host=settings.clamav_host, port=settings.clamav_port)
