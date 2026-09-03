#!/usr/bin/env python3
"""
Unit Test Suite for CTCAE v5.0 Adverse Event Triage & DLT Engine
================================================================
Comprehensive test suite verifying laboratory and symptom grading,
DLT determinations, Hy's Law assessment, irAE steroid management, and CLI workflows.
"""

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if ROOT_DIR.name == "tests":
    ROOT_DIR = ROOT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ctcae_triager import (
    CTCAEGrade,
    ActionTriage,
    AdverseEventInput,
    GradedAdverseEvent,
    HysLawAssessment,
    DLTAssessment,
    PatientSafetyReport,
    CTCAEGradingEngine,
    DLTEvaluator,
    ClinicalActionEngine,
    CTCAETriageEngine,
)
import cli


class TestCTCAELabGrading(unittest.TestCase):
    """Test quantitative laboratory threshold classification rules."""

    def test_neutropenia_grades(self):
        # Grade 4: < 500
        g4, r4 = CTCAEGradingEngine.grade_anc(400.0)
        self.assertEqual(g4, 4)
        # Grade 3: 500 - 999
        g3, r3 = CTCAEGradingEngine.grade_anc(850.0)
        self.assertEqual(g3, 3)
        # Grade 2: 1000 - 1499
        g2, r2 = CTCAEGradingEngine.grade_anc(1200.0)
        self.assertEqual(g2, 2)
        # Grade 1: 1500 - <2000
        g1, r1 = CTCAEGradingEngine.grade_anc(1800.0)
        self.assertEqual(g1, 1)
        # Grade 0: >= 2000
        g0, r0 = CTCAEGradingEngine.grade_anc(3500.0)
        self.assertEqual(g0, 0)

    def test_thrombocytopenia_grades(self):
        g4, _ = CTCAEGradingEngine.grade_platelets(15000.0)
        self.assertEqual(g4, 4)
        g3, _ = CTCAEGradingEngine.grade_platelets(35000.0)
        self.assertEqual(g3, 3)
        g2, _ = CTCAEGradingEngine.grade_platelets(60000.0)
        self.assertEqual(g2, 2)
        g1, _ = CTCAEGradingEngine.grade_platelets(110000.0)
        self.assertEqual(g1, 1)
        g0, _ = CTCAEGradingEngine.grade_platelets(250000.0)
        self.assertEqual(g0, 0)

    def test_anemia_grades(self):
        g4, _ = CTCAEGradingEngine.grade_hemoglobin(6.0)
        self.assertEqual(g4, 4)
        g3, _ = CTCAEGradingEngine.grade_hemoglobin(7.5)
        self.assertEqual(g3, 3)
        # Transfusion indicated qualifies as Grade 3
        g3_tx, _ = CTCAEGradingEngine.grade_hemoglobin(8.5, has_transfusion=True)
        self.assertEqual(g3_tx, 3)
        g2, _ = CTCAEGradingEngine.grade_hemoglobin(9.2)
        self.assertEqual(g2, 2)
        g1, _ = CTCAEGradingEngine.grade_hemoglobin(11.0)
        self.assertEqual(g1, 1)
        g0, _ = CTCAEGradingEngine.grade_hemoglobin(13.5)
        self.assertEqual(g0, 0)

    def test_liver_enzymes_grades(self):
        # ALT ULN = 40
        g4, _ = CTCAEGradingEngine.grade_liver_enzymes(900.0, uln=40.0) # 22.5x
        self.assertEqual(g4, 4)
        g3, _ = CTCAEGradingEngine.grade_liver_enzymes(300.0, uln=40.0) # 7.5x
        self.assertEqual(g3, 3)
        g2, _ = CTCAEGradingEngine.grade_liver_enzymes(160.0, uln=40.0) # 4.0x
        self.assertEqual(g2, 2)
        g1, _ = CTCAEGradingEngine.grade_liver_enzymes(80.0, uln=40.0) # 2.0x
        self.assertEqual(g1, 1)
        g0, _ = CTCAEGradingEngine.grade_liver_enzymes(35.0, uln=40.0)
        self.assertEqual(g0, 0)

    def test_bilirubin_grades(self):
        # Bilirubin ULN = 1.2
        g4, _ = CTCAEGradingEngine.grade_bilirubin(15.0, uln=1.2) # >10x
        self.assertEqual(g4, 4)
        g3, _ = CTCAEGradingEngine.grade_bilirubin(5.0, uln=1.2)  # >3x
        self.assertEqual(g3, 3)
        g2, _ = CTCAEGradingEngine.grade_bilirubin(2.5, uln=1.2)  # >1.5x
        self.assertEqual(g2, 2)
        g1, _ = CTCAEGradingEngine.grade_bilirubin(1.5, uln=1.2)  # >1.0x
        self.assertEqual(g1, 1)

    def test_creatinine_grades(self):
        g4, _ = CTCAEGradingEngine.grade_creatinine(8.0, baseline=1.0)
        self.assertEqual(g4, 4)
        g3, _ = CTCAEGradingEngine.grade_creatinine(4.0, baseline=1.0)
        self.assertEqual(g3, 3)
        g2, _ = CTCAEGradingEngine.grade_creatinine(2.0, baseline=1.0)
        self.assertEqual(g2, 2)
        g1, _ = CTCAEGradingEngine.grade_creatinine(1.4, baseline=1.0)
        self.assertEqual(g1, 1)

    def test_qtc_grades(self):
        g3, _ = CTCAEGradingEngine.grade_qtc(515.0)
        self.assertEqual(g3, 3)
        # Delta > 60 ms also triggers Grade 3
        g3_delta, _ = CTCAEGradingEngine.grade_qtc(475.0, baseline_qtc=410.0) # Delta 65
        self.assertEqual(g3_delta, 3)
        g2, _ = CTCAEGradingEngine.grade_qtc(490.0)
        self.assertEqual(g2, 2)
        g1, _ = CTCAEGradingEngine.grade_qtc(465.0)
        self.assertEqual(g1, 1)


class TestCTCAESymptomGrading(unittest.TestCase):
    """Test qualitative symptom classification rules."""

    def test_life_threatening_symptom_grade_4(self):
        g, _ = CTCAEGradingEngine.grade_clinical_symptom("Dyspnea", ["intubation required", "mechanical ventilation"])
        self.assertEqual(g, 4)

    def test_severe_symptom_grade_3(self):
        g, _ = CTCAEGradingEngine.grade_clinical_symptom("Diarrhea", [">=7 stools per day", "hospitalization indicated"])
        self.assertEqual(g, 3)

    def test_moderate_symptom_grade_2(self):
        g, _ = CTCAEGradingEngine.grade_clinical_symptom("Nausea", ["limiting instrumental ADL", "scheduled antiemetics"])
        self.assertEqual(g, 2)

    def test_mild_symptom_grade_1(self):
        g, _ = CTCAEGradingEngine.grade_clinical_symptom("Fatigue", ["mild tiredness not interfering with ADL"])
        self.assertEqual(g, 1)


class TestDLTEvaluation(unittest.TestCase):
    """Test Dose-Limiting Toxicity criteria."""

    def test_febrile_neutropenia_is_dlt(self):
        inp = AdverseEventInput(term="Febrile Neutropenia", lab_value=600.0, temperature_c=38.8, grade=3)
        is_dlt, reasons = DLTEvaluator.assess_event_dlt(inp, grade=3)
        self.assertTrue(is_dlt)
        self.assertIn("Febrile Neutropenia", reasons[0])

    def test_persistent_grade_4_neutropenia_is_dlt(self):
        inp = AdverseEventInput(term="Neutropenia", lab_value=300.0, duration_days=6)
        is_dlt, _ = DLTEvaluator.assess_event_dlt(inp, grade=4)
        self.assertTrue(is_dlt)

    def test_transient_grade_4_neutropenia_less_than_5_days_not_dlt(self):
        inp = AdverseEventInput(term="Neutropenia", lab_value=350.0, duration_days=2)
        is_dlt, _ = DLTEvaluator.assess_event_dlt(inp, grade=4)
        self.assertFalse(is_dlt)

    def test_grade_4_thrombocytopenia_is_dlt(self):
        inp = AdverseEventInput(term="Thrombocytopenia", lab_value=18000.0)
        is_dlt, _ = DLTEvaluator.assess_event_dlt(inp, grade=4)
        self.assertTrue(is_dlt)

    def test_grade_3_thrombocytopenia_with_bleeding_is_dlt(self):
        inp = AdverseEventInput(term="Thrombocytopenia", lab_value=35000.0, has_bleeding=True)
        is_dlt, _ = DLTEvaluator.assess_event_dlt(inp, grade=3)
        self.assertTrue(is_dlt)

    def test_non_heme_grade_3_is_dlt(self):
        inp = AdverseEventInput(term="Pancreatitis", system_organ_class="Gastrointestinal disorders", grade=3)
        is_dlt, _ = DLTEvaluator.assess_event_dlt(inp, grade=3)
        self.assertTrue(is_dlt)

    def test_alopecia_grade_2_not_dlt(self):
        inp = AdverseEventInput(term="Alopecia", system_organ_class="Skin and subcutaneous tissue disorders")
        is_dlt, _ = DLTEvaluator.assess_event_dlt(inp, grade=2)
        self.assertFalse(is_dlt)


class TestHysLaw(unittest.TestCase):
    """Test Hy's Law Drug-Induced Liver Injury (DILI) rules."""

    def test_meets_hys_law_criteria(self):
        res = DLTEvaluator.evaluate_hys_law(alt=200.0, ast=180.0, bilirubin=3.0, alk_phos=90.0)
        self.assertIsNotNone(res)
        self.assertTrue(res.meets_hys_law)
        self.assertGreaterEqual(res.alt_ast_elevation_factor, 3.0)
        self.assertGreaterEqual(res.bili_elevation_factor, 2.0)

    def test_isolated_transaminase_does_not_meet_hys_law(self):
        res = DLTEvaluator.evaluate_hys_law(alt=300.0, ast=250.0, bilirubin=1.0, alk_phos=80.0)
        self.assertFalse(res.meets_hys_law)

    def test_cholestatic_elevation_does_not_meet_pure_hys_law(self):
        res = DLTEvaluator.evaluate_hys_law(alt=150.0, ast=140.0, bilirubin=3.5, alk_phos=300.0) # Alk Phos > 2x ULN
        self.assertFalse(res.meets_hys_law)


class TestClinicalActionAndIRAE(unittest.TestCase):
    """Test action triage and irAE steroid rules."""

    def test_grade_3_irae_colitis_triggers_steroids(self):
        inp = AdverseEventInput(term="Colitis", is_immune_mediated=True)
        action, guidance, steroid_ind = ClinicalActionEngine.get_management_action(inp, grade=3, is_dlt=True)
        self.assertTrue(steroid_ind)
        self.assertEqual(action, ActionTriage.HOLD_DOSE)
        self.assertIn("corticosteroid", guidance.lower())

    def test_grade_4_event_triggers_stat_hospitalization(self):
        inp = AdverseEventInput(term="Septic Shock", symptoms=["life-threatening hemodynamic collapse"])
        action, guidance, _ = ClinicalActionEngine.get_management_action(inp, grade=4, is_dlt=True)
        self.assertEqual(action, ActionTriage.URGENT_HOSPITALIZATION_STAT)

    def test_grade_4_irae_triggers_permanent_discontinuation(self):
        inp = AdverseEventInput(term="Pneumonitis", symptoms=["mechanical ventilation indicated"])
        action, guidance, steroid_ind = ClinicalActionEngine.get_management_action(inp, grade=4, is_dlt=True)
        self.assertEqual(action, ActionTriage.PERMANENT_DISCONTINUATION)
        self.assertTrue(steroid_ind)


class TestFullPatientEncounter(unittest.TestCase):
    """Test full patient encounter report generation."""

    def test_patient_encounter_report(self):
        events = [
            AdverseEventInput(term="Neutropenia", lab_value=400.0, temperature_c=38.5, duration_days=3),
            AdverseEventInput(term="ALT increased", lab_value=90.0),
        ]
        rep = CTCAETriageEngine.triage_patient_encounter("PT-8801", events, cycle_number=1)
        self.assertEqual(rep.patient_id, "PT-8801")
        self.assertTrue(rep.dlt_assessment.is_dlt)
        self.assertEqual(rep.highest_grade, 4)
        self.assertTrue(rep.dose_modification_required)
        self.assertIsInstance(rep.to_dict(), dict)
        self.assertIsInstance(rep.to_json(), str)


class TestCLIAndBatchProcessing(unittest.TestCase):
    """Test CLI commands, JSON serialization, and batch CSV processing."""

    def test_cli_demo(self):
        self.assertEqual(cli.main(["--demo"]), 0)

    def test_cli_evaluate_single(self):
        self.assertEqual(cli.main(["evaluate", "--term", "Neutropenia", "--lab-value", "450"]), 0)

    def test_cli_triage_patient(self):
        payload = json.dumps([{"term": "Nausea", "symptoms": ["mild"]}, {"term": "Fatigue", "symptoms": ["mild"]}])
        self.assertEqual(cli.main(["triage", "--patient-id", "PT-TEST-01", "--payload", payload]), 0)

    def test_batch_csv_processing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_csv = os.path.join(tmpdir, "events_in.csv")
            out_csv = os.path.join(tmpdir, "events_out.csv")
            with open(in_csv, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["patient_id", "term", "system_organ_class", "lab_value", "symptoms", "duration_days", "is_immune_mediated"])
                writer.writerow(["PT-01", "Neutropenia", "Blood and lymphatic", "420", "", "5", "false"])
                writer.writerow(["PT-02", "Colitis", "Gastrointestinal", "", ">=7 stools per day", "3", "true"])

            ret = cli.main(["batch", "--input", in_csv, "--output", out_csv])
            self.assertEqual(ret, 0)
            self.assertTrue(os.path.exists(out_csv))
            with open(out_csv, "r") as f_out:
                lines = f_out.readlines()
                self.assertEqual(len(lines), 3)

    def test_cli_evaluate_json(self):
        import io
        out = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = out
        try:
            res = cli.main(["evaluate", "--term", "Neutropenia", "--lab-value", "450", "--json"])
            self.assertEqual(res, 0)
        finally:
            sys.stdout = old_stdout

        data = json.loads(out.getvalue())
        self.assertEqual(data["term"], "Neutropenia")
        self.assertEqual(data["grade"], 4)

    def test_cli_sample_csv_batch(self):
        sample_path = ROOT_DIR / "sample.csv"
        with tempfile.TemporaryDirectory() as tmpdir:
            out_csv = os.path.join(tmpdir, "output.csv")
            ret = cli.main(["batch", "--input", str(sample_path), "--output", out_csv])
            self.assertEqual(ret, 0)
            self.assertTrue(os.path.exists(out_csv))


if __name__ == "__main__":
    unittest.main()

