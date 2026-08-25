from ingestion.matching import match_student_by_name_in_text
from models.family import Family
from models.student import Student, StudentStatus


def test_matches_when_exactly_one_active_student_name_appears(db_session):
    family = Family(name="Familia Garcia")
    student = Student(family=family, name="Ana Garcia Lopez")
    db_session.add(family)
    db_session.commit()

    family_id, student_id = match_student_by_name_in_text(
        db_session, "Factura de transporte para Ana Garcia Lopez - Septiembre"
    )

    assert family_id == family.id
    assert student_id == student.id


def test_no_match_returns_none(db_session):
    family_id, student_id = match_student_by_name_in_text(db_session, "Texto sin ningun nombre")

    assert family_id is None
    assert student_id is None


def test_ambiguous_match_returns_none(db_session):
    family_a = Family(name="Familia A")
    family_b = Family(name="Familia B")
    db_session.add_all(
        [
            family_a,
            family_b,
            Student(family=family_a, name="Juan Perez"),
            Student(family=family_b, name="Juan Perez"),
        ]
    )
    db_session.commit()

    family_id, student_id = match_student_by_name_in_text(db_session, "Factura para Juan Perez")

    assert family_id is None
    assert student_id is None


def test_inactive_student_is_not_matched(db_session):
    family = Family(name="Familia Baja")
    db_session.add(family)
    db_session.commit()
    db_session.add(Student(family_id=family.id, name="Alumno Baja", status=StudentStatus.INACTIVE))
    db_session.commit()

    family_id, student_id = match_student_by_name_in_text(db_session, "Factura para Alumno Baja")

    assert family_id is None
    assert student_id is None
