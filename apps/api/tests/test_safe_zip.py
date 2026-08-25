import zipfile

import pytest

from ingestion.safe_zip import SafeZipLimits, UnsafeArchiveError, safe_extract_zip


def _make_zip(tmp_path, files: dict[str, bytes]) -> str:
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return str(zip_path)


def test_extracts_normal_zip(tmp_path):
    zip_path = _make_zip(tmp_path, {"factura.pdf": b"contenido factura", "nota.xml": b"<xml/>"})

    extracted = safe_extract_zip(zip_path, tmp_path / "out")

    names = {p.name for p in extracted}
    assert names == {"factura.pdf", "nota.xml"}
    assert (tmp_path / "out" / "factura.pdf").read_bytes() == b"contenido factura"


def test_rejects_too_many_files(tmp_path):
    zip_path = _make_zip(tmp_path, {f"f{i}.pdf": b"x" for i in range(5)})

    with pytest.raises(UnsafeArchiveError, match="ficheros"):
        safe_extract_zip(zip_path, tmp_path / "out", limits=SafeZipLimits(max_files=3))


def test_rejects_total_size_over_limit(tmp_path):
    zip_path = _make_zip(tmp_path, {"grande.pdf": b"x" * 1000})

    with pytest.raises(UnsafeArchiveError, match="bytes"):
        safe_extract_zip(
            zip_path, tmp_path / "out", limits=SafeZipLimits(max_total_uncompressed_bytes=500)
        )


def test_rejects_high_compression_ratio(tmp_path):
    # Muy compresible (bytes repetidos) -> ratio de compresión alto.
    zip_path = _make_zip(tmp_path, {"sospechoso.bin": b"A" * 1_000_000})

    with pytest.raises(UnsafeArchiveError, match="ratio"):
        safe_extract_zip(zip_path, tmp_path / "out", limits=SafeZipLimits(max_compression_ratio=10))


def test_flattens_paths_to_prevent_traversal(tmp_path):
    zip_path = _make_zip(tmp_path, {"../../etc/passwd": b"malicioso"})

    extracted = safe_extract_zip(zip_path, tmp_path / "out")

    assert extracted[0].parent == tmp_path / "out"
    assert extracted[0].name == "passwd"
