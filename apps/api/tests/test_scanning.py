from ingestion.scanning import NoOpScanner


def test_noop_scanner_always_reports_clean_and_says_so(tmp_path):
    target = tmp_path / "cualquier_fichero.pdf"
    target.write_bytes(b"contenido")

    result = NoOpScanner().scan(target)

    assert result.clean is True
    assert "sin escaneo real" in result.detail
