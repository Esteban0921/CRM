from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path


class UnsafeArchiveError(Exception):
    pass


@dataclass
class SafeZipLimits:
    max_files: int = 50
    max_total_uncompressed_bytes: int = 200 * 1024 * 1024
    max_compression_ratio: int = 100


DEFAULT_LIMITS = SafeZipLimits()


def safe_extract_zip(
    zip_path: str | Path,
    dest_dir: str | Path,
    limits: SafeZipLimits = DEFAULT_LIMITS,
) -> list[Path]:
    """Extrae un ZIP con límites anti zip-bomb (RULE-016 de AGENTS.md).

    Falla ANTES de escribir nada si se supera algún límite: nº de ficheros,
    tamaño total descomprimido, o ratio de compresión de un miembro.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]

        if len(infos) > limits.max_files:
            raise UnsafeArchiveError(
                f"El ZIP tiene {len(infos)} ficheros, el límite es {limits.max_files}"
            )

        total_uncompressed = 0
        for info in infos:
            total_uncompressed += info.file_size
            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > limits.max_compression_ratio:
                    raise UnsafeArchiveError(
                        f"'{info.filename}' tiene ratio de compresión {ratio:.0f}:1, "
                        f"el límite es {limits.max_compression_ratio}:1"
                    )

        if total_uncompressed > limits.max_total_uncompressed_bytes:
            raise UnsafeArchiveError(
                f"El ZIP descomprime a {total_uncompressed} bytes, "
                f"el límite es {limits.max_total_uncompressed_bytes}"
            )

        extracted: list[Path] = []
        for info in infos:
            # Path(info.filename).name descarta subcarpetas: evita path
            # traversal (../../etc/passwd) desde dentro del ZIP.
            target = dest / Path(info.filename).name
            with archive.open(info) as source, open(target, "wb") as out:
                out.write(source.read())
            extracted.append(target)

    return extracted
