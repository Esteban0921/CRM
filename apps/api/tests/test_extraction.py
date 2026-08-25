from ingestion.extraction import ExtractionTemplate, extract_fields


def test_generic_extraction_finds_common_fields():
    text = """
    FACTURA
    Factura Nº: INV-2026-045
    Fecha: 01/09/2026
    NIF: B12345678
    Total: 45,00 EUR
    """

    result = extract_fields(text)

    assert result.invoice_number == "INV-2026-045"
    assert result.issue_date == "01/09/2026"
    assert result.tax_id == "B12345678"
    assert result.confidence > 0


def test_no_matches_gives_zero_confidence():
    result = extract_fields("Este documento no tiene ningún campo reconocible.")

    assert result.confidence == 0.0
    assert result.invoice_number is None


def test_matching_template_gives_higher_confidence_than_generic():
    text = "TransBus S.L. - Recibo mensual - Ref: TB-9001 - Fecha: 01/09/2026 - Total: 40,00"
    template = ExtractionTemplate(
        name="transbus",
        keywords=["transbus"],
        patterns={
            "invoice_number": r"Ref:\s*([A-Z0-9\-]+)",
            "issue_date": r"Fecha:\s*(\d{1,2}/\d{1,2}/\d{4})",
            "total_amount": r"Total:\s*([\d.,]+)",
        },
    )

    generic_result = extract_fields(text)
    templated_result = extract_fields(text, templates=[template])

    assert templated_result.invoice_number == "TB-9001"
    assert templated_result.confidence > generic_result.confidence
