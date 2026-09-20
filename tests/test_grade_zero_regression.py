from ctcae_triager import AdverseEventInput, CTCAETriageEngine


def test_explicit_grade_zero_is_preserved():
    event = AdverseEventInput(term="Neutropenia", grade=0, lab_value=450.0)
    graded = CTCAETriageEngine.evaluate_single_event(event)
    assert graded.grade == 0
    assert graded.grade_name == "Grade 0 (Normal / None)"
    assert graded.is_dlt is False
