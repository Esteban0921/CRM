"""Regresiones de la ingesta (TASK-0090, 0115, 0116, 0117).

Son los tres caminos por los que entraba un dato equivocado en la base de
datos, mas el adjunto que tumbaba el proceso. Cada test falla contra el codigo
anterior a su arreglo.
"""

import time

from ingestion.extraction import extract_fields, parse_spanish_amount
from ingestion.matching import name_appears_in, normalize
from models.family import Family
from models.student import Student, StudentStatus

# --- TASK-0115: «Subtotal» no es «Total» ----------------------------------

FACTURA_CON_IVA = """
FACTURA F-2026-001
Fecha: 05/09/2026
NIF: B12345678
Subtotal: 100,00
IVA 21%: 21,00
Total: 121,00 EUR
"""


def test_el_total_no_se_confunde_con_el_subtotal():
    fields = extract_fields(FACTURA_CON_IVA)

    assert fields.total_amount == "121,00", (
        "se cogio la base imponible: la factura entraria en el sistema sin IVA"
    )
    assert parse_spanish_amount(fields.total_amount) == parse_spanish_amount("121,00")


def test_el_total_no_se_confunde_con_el_total_de_iva():
    texto = "Base: 100,00\nTotal IVA: 21,00\nTotal: 121,00 EUR\n"

    assert extract_fields(texto).total_amount == "121,00"


def test_una_factura_sin_subtotal_sigue_funcionando():
    texto = "FACTURA A-1\nFecha: 01/09/2026\nTotal: 45,00 EUR\n"

    assert extract_fields(texto).total_amount == "45,00"


# --- TASK-0116: separador de miles ----------------------------------------


def test_mil_doscientos_treinta_y_cuatro_no_es_un_euro_con_veintitres():
    assert parse_spanish_amount("1.234") == parse_spanish_amount("1234")


def test_los_decimales_con_punto_siguen_siendo_decimales():
    assert str(parse_spanish_amount("45.00")) == "45.00"


def test_formatos_habituales_de_importe():
    casos = {
        "45,00": "45.00",
        "1.234,56": "1234.56",
        "1,234.56": "1234.56",
        "1.234": "1234",
        "1.234.567,89": "1234567.89",
        "0,50": "0.50",
    }
    for raw, esperado in casos.items():
        assert parse_spanish_amount(raw) == parse_spanish_amount(esperado), raw


# --- TASK-0117: matching de alumno ----------------------------------------


def test_ana_no_empareja_dentro_de_semana():
    assert not name_appears_in("Ana", "Servicio de la semana pasada, ruta manana")


def test_un_nombre_completo_si_empareja():
    assert name_appears_in("Ana Garcia Perez", "Transporte de Ana Garcia Perez, septiembre")


def test_el_matching_ignora_acentos_y_mayusculas():
    assert name_appears_in("Jose Nunez", "Alumno: JOSÉ NÚÑEZ")
    assert name_appears_in("José Núñez", "alumno: jose nunez")


def test_normalize_quita_acentos():
    assert normalize("JOSÉ NÚÑEZ") == "jose nunez"


def test_una_factura_sin_nombre_de_alumno_no_se_enlaza(db_session):
    """El caso real de la auditoria: un PDF sin ningun nombre acabo enlazado a
    la familia del alumno «Ana» por aparecer dentro de «semana» y «manana».
    """
    from ingestion.matching import match_student_by_name_in_text

    family = Family(name="Familia Beta")
    db_session.add(family)
    db_session.commit()
    db_session.add(Student(family_id=family.id, name="Ana", status=StudentStatus.ACTIVE))
    db_session.commit()

    family_id, student_id = match_student_by_name_in_text(
        db_session, "Total: 10,00 EUR\nServicio de la semana pasada, ruta manana"
    )

    assert family_id is None
    assert student_id is None


# --- TASK-0090: ReDoS ------------------------------------------------------


def test_un_adjunto_hostil_no_congela_la_extraccion():
    """Payload de la auditoria: con los cuantificadores adyacentes originales,
    400 KB tardaban 70 s y paraban toda la API porque `re` no suelta el GIL.
    """
    hostil = "factura" + " " * 4000 + "A" * 400_000

    inicio = time.perf_counter()
    extract_fields(hostil)
    transcurrido = time.perf_counter() - inicio

    assert transcurrido < 2.0, f"la extraccion tardo {transcurrido:.1f}s"


def test_el_texto_se_recorta_antes_de_pasar_por_los_regex():
    from config import settings

    enorme = "Total: 45,00 EUR\n" + "x" * (settings.max_extraction_text_bytes * 2)

    inicio = time.perf_counter()
    fields = extract_fields(enorme)
    transcurrido = time.perf_counter() - inicio

    assert fields.total_amount == "45,00"
    assert transcurrido < 2.0
