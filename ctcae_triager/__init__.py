#!/usr/bin/env python3
"""
CTCAE v5.0 Adverse Event Triage & Dose-Limiting Toxicity (DLT) Engine
====================================================================
Pure-standard-library screening helpers for selected CTCAE v5.0 laboratory
thresholds, symptom-severity heuristics, protocol-style DLT checks, Hy's Law
laboratory signal screening, and irAE-oriented management prompts.

This package is not a complete CTCAE dictionary, protocol implementation, or
clinical decision system. Protocol-specific definitions, local laboratory
reference ranges, causality assessment, and clinician judgment remain required.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

__version__ = "2.1.0"


# ============================================================================
# Utility Functions
# ============================================================================

def safe_resolve_path(file_path: str, must_exist: bool = False) -> Path:
    """Normalize a user-supplied path and optionally validate an input file.

    This function does not sandbox the caller to the current working directory;
    command-line users may intentionally read or write paths elsewhere.
    """
    p = Path(file_path).resolve()
    if must_exist and not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if must_exist and not p.is_file():
        raise ValueError(f"Path is not a regular file: {file_path}")
    return p


# ============================================================================
# Enums & Constants
# ============================================================================

class CTCAEGrade(int, Enum):
    GRADE_0_NONE = 0
    GRADE_1_MILD = 1
    GRADE_2_MODERATE = 2
    GRADE_3_SEVERE = 3
    GRADE_4_LIFE_THREATENING = 4
    GRADE_5_DEATH = 5


class Causality(str, Enum):
    DEFINITELY_RELATED = "DEFINITELY_RELATED"
    PROBABLY_RELATED = "PROBABLY_RELATED"
    POSSIBLY_RELATED = "POSSIBLY_RELATED"
    UNLIKELY_RELATED = "UNLIKELY_RELATED"
    UNRELATED = "UNRELATED"


class ActionTriage(str, Enum):
    CONTINUE_MONITORING = "CONTINUE_MONITORING"
    SUPPORTIVE_CARE = "SUPPORTIVE_CARE"
    HOLD_DOSE = "HOLD_DOSE"
    DOSE_REDUCE_LEVEL_1 = "DOSE_REDUCE_LEVEL_1"  # -25%
    DOSE_REDUCE_LEVEL_2 = "DOSE_REDUCE_LEVEL_2"  # -50%
    PERMANENT_DISCONTINUATION = "PERMANENT_DISCONTINUATION"
    URGENT_HOSPITALIZATION_STAT = "URGENT_HOSPITALIZATION_STAT"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class AdverseEventInput:
    """Input representation of an adverse event."""
    term: str
    system_organ_class: str = "General disorders"
    grade: Optional[int] = None
    lab_value: Optional[float] = None
    baseline_value: Optional[float] = None
    unit: str = ""
    symptoms: List[str] = field(default_factory=list)
    onset_day: int = 1
    resolution_day: Optional[int] = None
    duration_days: Optional[int] = None
    causality: str = "PROBABLY_RELATED"
    is_immune_mediated: bool = False
    has_bleeding: bool = False
    temperature_c: Optional[float] = None

    def __post_init__(self):
        if not self.term or not self.term.strip():
            raise ValueError("Adverse event term must be a non-empty string.")
        if self.grade is not None and (
            isinstance(self.grade, bool)
            or not isinstance(self.grade, int)
            or not 0 <= self.grade <= 5
        ):
            raise ValueError(f"grade must be an integer from 0 through 5, got {self.grade!r}.")
        if not isinstance(self.symptoms, list) or not all(isinstance(item, str) for item in self.symptoms):
            raise ValueError("symptoms must be a list of strings.")
        if self.lab_value is not None and (self.lab_value < 0 or math.isnan(self.lab_value) or math.isinf(self.lab_value)):
            raise ValueError(f"lab_value must be a non-negative finite number, got {self.lab_value}.")
        if self.baseline_value is not None and (self.baseline_value < 0 or math.isnan(self.baseline_value) or math.isinf(self.baseline_value)):
            raise ValueError(f"baseline_value must be a non-negative finite number, got {self.baseline_value}.")
        if self.temperature_c is not None and (self.temperature_c < 30.0 or self.temperature_c > 45.0):
            raise ValueError(f"temperature_c must be between 30.0 and 45.0 Celsius, got {self.temperature_c}.")
        if self.duration_days is None:
            if self.resolution_day is not None and self.resolution_day >= self.onset_day:
                self.duration_days = self.resolution_day - self.onset_day + 1
            else:
                self.duration_days = 1
        if self.duration_days < 1:
            raise ValueError(f"duration_days must be at least 1, got {self.duration_days}.")


@dataclass
class GradedAdverseEvent:
    """Evaluated Adverse Event with CTCAE v5.0 Grade and Clinical Rationale."""
    term: str
    system_organ_class: str
    grade: int
    grade_name: str
    is_serious: bool
    is_dlt: bool
    dlt_reasons: List[str]
    management_guidance: str
    action_triage: str
    rationale: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HysLawAssessment:
    """Hy's Law DILI criteria: ALT/AST >= 3x ULN + Total Bilirubin >= 2x ULN + Alk Phos < 2x ULN."""
    meets_hys_law: bool
    alt_ast_elevation_factor: float
    bili_elevation_factor: float
    alk_phos_elevation_factor: Optional[float]
    rationale: str


@dataclass
class DLTAssessment:
    """Comprehensive Dose-Limiting Toxicity evaluation."""
    is_dlt: bool
    total_dlt_events: int
    dlt_criteria_met: List[str]
    highest_grade: int
    affected_organs: List[str]
    clinical_recommendation: str
    action_triage: str


@dataclass
class PatientSafetyReport:
    """Full triage report for a clinical trial patient encounter."""
    patient_id: str
    cycle_number: int
    total_events: int
    highest_grade: int
    grade_distribution: Dict[int, int]
    graded_events: List[GradedAdverseEvent]
    dlt_assessment: DLTAssessment
    hys_law: Optional[HysLawAssessment]
    dose_modification_required: bool
    recommended_action: str
    irae_steroid_indicated: bool
    narrative_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ============================================================================
# CTCAE v5.0 Laboratory & Symptom Grading Rules
# ============================================================================

class CTCAEGradingEngine:
    """
    Implements selected quantitative CTCAE v5.0 thresholds and conservative
    symptom-description heuristics. It is not a complete CTCAE implementation.
    """

    # Reference Standard Upper/Lower Limits of Normal (ULN/LLN)
    STANDARD_LIMITS = {
        "anc": {"lln": 2000.0, "unit": "/mm3"},
        "platelets": {"lln": 150000.0, "unit": "/mm3"},
        "hemoglobin": {"lln": 12.0, "unit": "g/dL"},
        "alt": {"uln": 40.0, "unit": "U/L"},
        "ast": {"uln": 40.0, "unit": "U/L"},
        "bilirubin": {"uln": 1.2, "unit": "mg/dL"},
        "alk_phos": {"uln": 120.0, "unit": "U/L"},
        "creatinine": {"uln": 1.2, "unit": "mg/dL"},
        "sodium_low": {"lln": 135.0, "unit": "mmol/L"},
        "potassium_high": {"uln": 5.0, "unit": "mmol/L"},
        "calcium_low": {"lln": 8.5, "unit": "mg/dL"},
        "qtc": {"uln": 450.0, "unit": "ms"},
    }

    @classmethod
    def grade_anc(cls, value: float) -> Tuple[int, str]:
        """Absolute Neutrophil Count (/mm³ or /µL)."""
        if value < 500.0:
            return 4, f"ANC < 500/mm³ ({value:.0f}/mm³): Grade 4 (Life-threatening neutropenia)"
        elif value < 1000.0:
            return 3, f"ANC 500-999/mm³ ({value:.0f}/mm³): Grade 3 (Severe neutropenia)"
        elif value < 1500.0:
            return 2, f"ANC 1000-1499/mm³ ({value:.0f}/mm³): Grade 2 (Moderate neutropenia)"
        elif value < cls.STANDARD_LIMITS["anc"]["lln"]:
            return 1, f"ANC < LLN-1500/mm³ ({value:.0f}/mm³): Grade 1 (Mild neutropenia)"
        return 0, f"ANC within normal limits ({value:.0f}/mm³)"

    @classmethod
    def grade_platelets(cls, value: float) -> Tuple[int, str]:
        """Platelet Count (/mm³ or /µL)."""
        if value < 25000.0:
            return 4, f"Platelets < 25,000/mm³ ({value:.0f}/mm³): Grade 4 (Severe life-threatening thrombocytopenia)"
        elif value < 50000.0:
            return 3, f"Platelets 25,000-49,999/mm³ ({value:.0f}/mm³): Grade 3 (Severe thrombocytopenia)"
        elif value < 75000.0:
            return 2, f"Platelets 50,000-74,999/mm³ ({value:.0f}/mm³): Grade 2 (Moderate thrombocytopenia)"
        elif value < cls.STANDARD_LIMITS["platelets"]["lln"]:
            return 1, f"Platelets < LLN-75,000/mm³ ({value:.0f}/mm³): Grade 1 (Mild thrombocytopenia)"
        return 0, f"Platelets within normal limits ({value:.0f}/mm³)"

    @classmethod
    def grade_hemoglobin(cls, value: float, has_transfusion: bool = False) -> Tuple[int, str]:
        """Hemoglobin (g/dL)."""
        if value < 6.5:
            return 4, f"Hemoglobin < 6.5 g/dL ({value:.1f} g/dL): Grade 4 (Life-threatening anemia)"
        elif value < 8.0 or has_transfusion:
            return 3, f"Hemoglobin < 8.0 g/dL ({value:.1f} g/dL) or transfusion indicated: Grade 3 (Severe anemia)"
        elif value < 10.0:
            return 2, f"Hemoglobin 8.0-9.9 g/dL ({value:.1f} g/dL): Grade 2 (Moderate anemia)"
        elif value < cls.STANDARD_LIMITS["hemoglobin"]["lln"]:
            return 1, f"Hemoglobin < LLN-10.0 g/dL ({value:.1f} g/dL): Grade 1 (Mild anemia)"
        return 0, f"Hemoglobin within normal limits ({value:.1f} g/dL)"

    @classmethod
    def grade_liver_enzymes(cls, alt_or_ast: float, uln: float = 40.0, enzyme_name: str = "ALT") -> Tuple[int, str]:
        """ALT or AST elevation (x ULN)."""
        if uln <= 0:
            raise ValueError(f"ULN must be positive, got {uln}.")
        ratio = alt_or_ast / uln
        if ratio > 20.0:
            return 4, f"{enzyme_name} > 20.0x ULN ({ratio:.1f}x ULN, {alt_or_ast:.1f} U/L): Grade 4"
        elif ratio > 5.0:
            return 3, f"{enzyme_name} > 5.0-20.0x ULN ({ratio:.1f}x ULN, {alt_or_ast:.1f} U/L): Grade 3"
        elif ratio > 3.0:
            return 2, f"{enzyme_name} > 3.0-5.0x ULN ({ratio:.1f}x ULN, {alt_or_ast:.1f} U/L): Grade 2"
        elif ratio > 1.0:
            return 1, f"{enzyme_name} > 1.0-3.0x ULN ({ratio:.1f}x ULN, {alt_or_ast:.1f} U/L): Grade 1"
        return 0, f"{enzyme_name} within normal limits ({alt_or_ast:.1f} U/L)"

    @classmethod
    def grade_bilirubin(cls, value: float, uln: float = 1.2) -> Tuple[int, str]:
        """Total Bilirubin elevation (x ULN)."""
        if uln <= 0:
            raise ValueError(f"ULN must be positive, got {uln}.")
        ratio = value / uln
        if ratio > 10.0:
            return 4, f"Bilirubin > 10.0x ULN ({ratio:.1f}x ULN, {value:.2f} mg/dL): Grade 4"
        elif ratio > 3.0:
            return 3, f"Bilirubin > 3.0-10.0x ULN ({ratio:.1f}x ULN, {value:.2f} mg/dL): Grade 3"
        elif ratio > 1.5:
            return 2, f"Bilirubin > 1.5-3.0x ULN ({ratio:.1f}x ULN, {value:.2f} mg/dL): Grade 2"
        elif ratio > 1.0:
            return 1, f"Bilirubin > 1.0-1.5x ULN ({ratio:.1f}x ULN, {value:.2f} mg/dL): Grade 1"
        return 0, f"Bilirubin within normal limits ({value:.2f} mg/dL)"

    @classmethod
    def grade_creatinine(cls, value: float, baseline: Optional[float] = None, uln: float = 1.2) -> Tuple[int, str]:
        """CTCAE v5.0 creatinine increased grading using ULN and baseline ratios."""
        if uln <= 0:
            raise ValueError(f"ULN must be positive, got {uln}.")
        if baseline is not None and baseline <= 0:
            raise ValueError(f"baseline must be positive when provided, got {baseline}.")

        uln_ratio = value / uln
        baseline_ratio = (value / baseline) if baseline is not None else None

        if uln_ratio > 6.0:
            return 4, f"Creatinine > 6.0x ULN ({uln_ratio:.1f}x ULN, {value:.2f} mg/dL): Grade 4"
        if (baseline_ratio is not None and baseline_ratio > 3.0) or uln_ratio > 3.0:
            return 3, (
                f"Creatinine > 3.0x baseline or > 3.0-6.0x ULN "
                f"(baseline ratio={baseline_ratio:.1f}x, ULN ratio={uln_ratio:.1f}x): Grade 3"
                if baseline_ratio is not None
                else f"Creatinine > 3.0-6.0x ULN ({uln_ratio:.1f}x ULN): Grade 3"
            )
        if (baseline_ratio is not None and baseline_ratio > 1.5) or uln_ratio > 1.5:
            return 2, (
                f"Creatinine > 1.5-3.0x baseline or > 1.5-3.0x ULN "
                f"(baseline ratio={baseline_ratio:.1f}x, ULN ratio={uln_ratio:.1f}x): Grade 2"
                if baseline_ratio is not None
                else f"Creatinine > 1.5-3.0x ULN ({uln_ratio:.1f}x ULN): Grade 2"
            )
        if uln_ratio > 1.0:
            return 1, f"Creatinine > ULN-1.5x ULN ({uln_ratio:.1f}x ULN, {value:.2f} mg/dL): Grade 1"
        return 0, f"Creatinine within reference range ({value:.2f} mg/dL)"

    @classmethod
    def grade_qtc(cls, qtc_ms: float, baseline_qtc: Optional[float] = None) -> Tuple[int, str]:
        """QTc Prolongation (Fridericia or Bazett, ms)."""
        delta = (qtc_ms - baseline_qtc) if baseline_qtc else 0.0
        if qtc_ms >= 501.0 or delta >= 61.0:
            return 3, f"QTc >= 501 ms ({qtc_ms:.0f} ms, Delta={delta:.0f} ms): Grade 3 (Severe QTc prolongation)"
        elif qtc_ms >= 481.0 or (30.0 <= delta <= 60.0):
            return 2, f"QTc 481-500 ms ({qtc_ms:.0f} ms): Grade 2 (Moderate QTc prolongation)"
        elif qtc_ms >= 450.0:
            return 1, f"QTc 450-480 ms ({qtc_ms:.0f} ms): Grade 1 (Mild QTc prolongation)"
        return 0, f"QTc normal ({qtc_ms:.0f} ms)"

    @classmethod
    def grade_clinical_symptom(cls, term: str, symptoms: List[str]) -> Tuple[int, str]:
        """Classify subjective symptoms using CTCAE v5.0 keyword anchors."""
        text = " ".join([term] + symptoms).lower()

        # Grade 4 anchors
        if any(w in text for w in [
            "life-threatening", "hemodynamic collapse", "intubation", "mechanical ventilation",
            "perforation", "dialysis", "grade 4", "emergency intervention", "septic shock",
            "torsades", "stevens-johnson", "toxic epidermal necrolysis"
        ]):
            return 4, f"Grade 4 symptom severity identified in clinical description for {term}."

        # Grade 3 anchors
        if any(w in text for w in [
            "hospitalization", "iv hydration", "limiting self care adl", "oxygen indicated",
            "transfusion", "grade 3", "severe pain", "severe ulceration", "incontinence",
            ">=7 stools", "7 or more stools", "systemic steroids", "gross hematuria"
        ]):
            return 3, f"Grade 3 medically significant severity for {term}."

        # Grade 2 anchors
        if any(w in text for w in [
            "limiting instrumental adl", "minimal intervention", "scheduled medications",
            "grade 2", "moderate", "4-6 stools", "4 to 6 stools", "dietary alteration",
            "steroid cream", "oral intake decreased"
        ]):
            return 2, f"Grade 2 moderate severity for {term}."

        # Grade 1 anchors
        if any(w in text for w in ["mild", "asymptomatic", "grade 1", "loss of appetite", "no intervention", "<4 stools"]):
            return 1, f"Grade 1 mild severity for {term}."

        # Default to Grade 1 if no specific anchor found
        return 1, f"Defaulting to Grade 1 mild severity for {term} based on available notes."


# ============================================================================
# Dose-Limiting Toxicity (DLT) & Safety Evaluator
# ============================================================================

class DLTEvaluator:
    """
    Oncology Phase I / II Dose-Limiting Toxicity (DLT) rules engine.
    Applies standard NCI CTEP and clinical trial protocol criteria:
    - Any Grade 4 hematologic toxicity lasting >= 5-7 days
    - Febrile neutropenia (ANC < 1000/mm³ + Temp > 38.3°C or >= 38.0°C for > 1hr)
    - Grade 4 thrombocytopenia OR Grade 3 thrombocytopenia with bleeding
    - Any Grade >= 3 non-hematologic toxicity (excluding nausea/vomiting/alopecia controlled by therapy)
    - Grade >= 3 hepatotoxicity or Hy's Law
    - Treatment delay > 14 days due to unresolved toxicity
    - Any Grade 5 toxicity
    """

    @classmethod
    def evaluate_hys_law(
        cls,
        alt: Optional[float],
        ast: Optional[float],
        bilirubin: Optional[float],
        alk_phos: Optional[float] = None,
    ) -> Optional[HysLawAssessment]:
        """
        FDA / Zimmerman Hy's Law criteria:
        1. ALT or AST >= 3x ULN
        2. Total Bilirubin >= 2x ULN
        3. Alkaline Phosphatase < 2x ULN (ruling out cholestatic injury)
        """
        if alt is None and ast is None:
            return None

        alt_val = alt if alt is not None else 0.0
        ast_val = ast if ast is not None else 0.0
        max_transaminase = max(alt_val, ast_val)
        bili_val = bilirubin if bilirubin is not None else 0.0

        trans_ratio = max_transaminase / 40.0
        bili_ratio = bili_val / 1.2
        alk_ratio = (alk_phos / 120.0) if alk_phos is not None else None

        signal = (trans_ratio >= 3.0) and (bili_ratio >= 2.0)
        meets = signal and alk_ratio is not None and alk_ratio < 2.0

        if meets:
            rationale = (
                f"Hy's Law laboratory screening thresholds are met: ALT/AST {trans_ratio:.1f}x ULN, "
                f"total bilirubin {bili_ratio:.1f}x ULN, and alkaline phosphatase {alk_ratio:.1f}x ULN. "
                "This is a screening signal only; alternative causes of liver injury are not assessed here."
            )
        elif signal and alk_ratio is None:
            rationale = (
                f"Potential Hy's Law laboratory signal: ALT/AST {trans_ratio:.1f}x ULN and total bilirubin "
                f"{bili_ratio:.1f}x ULN, but alkaline phosphatase is missing, so cholestasis cannot be screened out."
            )
        else:
            alk_text = "not provided" if alk_ratio is None else f"{alk_ratio:.1f}x ULN"
            rationale = (
                f"Hy's Law laboratory screening thresholds are not met "
                f"(transaminases {trans_ratio:.1f}x ULN, bilirubin {bili_ratio:.1f}x ULN, ALP {alk_text})."
            )

        return HysLawAssessment(
            meets_hys_law=meets,
            alt_ast_elevation_factor=round(trans_ratio, 2),
            bili_elevation_factor=round(bili_ratio, 2),
            alk_phos_elevation_factor=round(alk_ratio, 2) if alk_ratio is not None else None,
            rationale=rationale,
        )

    @classmethod
    def assess_event_dlt(cls, event: AdverseEventInput, grade: int) -> Tuple[bool, List[str]]:
        """Determine if an individual event qualifies as a DLT."""
        reasons = []
        term_lower = event.term.lower()
        soc_lower = event.system_organ_class.lower()
        is_heme = any(k in term_lower or k in soc_lower for k in ["neutropen", "thrombocytopen", "anemia", "leukopen", "hematolog"])

        # 1. Grade 5 (Death)
        if grade == 5:
            reasons.append("Grade 5 fatal event related to study drug.")

        # 2. Febrile Neutropenia
        if "febrile neutropenia" in term_lower or (
            "neutropen" in term_lower and event.temperature_c is not None and event.temperature_c >= 38.0 and grade >= 3
        ):
            reasons.append("Febrile Neutropenia (ANC < 1000/mm³ with fever >= 38.0°C).")

        # 3. Hematologic DLTs
        if is_heme:
            if "thrombocytopen" in term_lower:
                if grade >= 4:
                    reasons.append(f"Grade 4 thrombocytopenia (Platelets < 25,000/mm³).")
                elif grade == 3 and event.has_bleeding:
                    reasons.append("Grade 3 thrombocytopenia associated with clinically significant bleeding.")
            elif "neutropen" in term_lower:
                if grade >= 4 and (event.duration_days is not None and event.duration_days >= 5):
                    reasons.append(f"Grade 4 neutropenia (ANC < 500/mm³) persisting >= 5 days ({event.duration_days} days).")
            elif grade >= 4:
                reasons.append(f"Grade 4 hematologic toxicity ({event.term}).")

        # 4. Non-Hematologic DLTs
        else:
            if grade >= 3:
                # Check for protocol exceptions (alopecia)
                if not any(exc in term_lower for exc in ["alopecia", "vitiligo"]):
                    if grade >= 4:
                        reasons.append(f"Grade 4 life-threatening non-hematologic toxicity ({event.term}).")
                    else:
                        reasons.append(f"Grade 3 non-hematologic toxicity ({event.term}).")

        # 5. Dose delay > 14 days
        if event.duration_days is not None and event.duration_days > 14 and grade >= 2:
            reasons.append(f"Toxicity resulting in treatment delay > 14 days ({event.duration_days} days).")

        is_dlt = len(reasons) > 0
        return is_dlt, reasons


# ============================================================================
# Clinical Action Triage & irAE Management
# ============================================================================

class ClinicalActionEngine:
    """Provides guideline-directed clinical management recommendations."""

    @classmethod
    def get_management_action(
        cls,
        event: AdverseEventInput,
        grade: int,
        is_dlt: bool,
    ) -> Tuple[ActionTriage, str, bool]:
        """
        Returns (ActionTriage, clinical_guidance_text, is_steroid_indicated).
        """
        term_lower = event.term.lower()
        steroid_indicated = False

        # irAE management must be explicitly selected by the caller. A term such
        # as "colitis" or "rash" does not establish immune-mediated causality.
        if event.is_immune_mediated:
            if grade >= 3:
                steroid_indicated = True
                action = ActionTriage.PERMANENT_DISCONTINUATION if grade == 4 else ActionTriage.HOLD_DOSE
                guidance = (
                    f"irAE Grade {grade}: Immediately HOLD checkpoint inhibitor; initiate high-dose corticosteroids "
                    f"(1.0 - 2.0 mg/kg/day prednisone or methylprednisolone equivalent); taper over >= 4-6 weeks once improved. "
                    f"{'Permanent discontinuation required.' if grade == 4 else 'Consider resuming when toxicity resolves to Grade <= 1.'}"
                )
                return action, guidance, steroid_indicated
            elif grade == 2:
                steroid_indicated = True
                return (
                    ActionTriage.HOLD_DOSE,
                    "irAE Grade 2: Hold study treatment; initiate oral prednisone 0.5 - 1.0 mg/kg/day; taper over 2-4 weeks; monitor closely.",
                    steroid_indicated,
                )
            elif grade == 1:
                return (
                    ActionTriage.CONTINUE_MONITORING,
                    "irAE Grade 1: Continue study therapy with close symptom monitoring and repeat laboratory testing weekly.",
                    False,
                )

        # Standard Chemotherapy / Targeted Therapy action triage
        if grade == 5:
            return ActionTriage.PERMANENT_DISCONTINUATION, "Grade 5 Event: Discontinue protocol therapy immediately. Complete SAE/FDA MedWatch reporting.", False

        if grade == 4:
            return (
                ActionTriage.URGENT_HOSPITALIZATION_STAT,
                f"Grade 4 {event.term}: STAT hospitalization and immediate resuscitation/intervention. Discontinue study drug.",
                False,
            )

        if is_dlt or grade == 3:
            return (
                ActionTriage.HOLD_DOSE,
                f"Grade 3 / DLT ({event.term}): Hold study drug until resolution to Grade <= 1 or baseline. Resume with Level -1 dose reduction (-25%).",
                False,
            )

        if grade == 2:
            return (
                ActionTriage.SUPPORTIVE_CARE,
                f"Grade 2 ({event.term}): Provide targeted supportive therapy (e.g. antiemetics, loperamide, topical emollients). Monitor weekly.",
                False,
            )

        return (
            ActionTriage.CONTINUE_MONITORING,
            f"Grade 1 ({event.term}): Continue current dose; non-invasive symptomatic management as needed.",
            False,
        )


# ============================================================================
# Main CTCAE Triage Master Engine
# ============================================================================

class CTCAETriageEngine:
    """Master engine orchestrating patient adverse event safety triage."""

    @classmethod
    def evaluate_single_event(cls, inp: AdverseEventInput) -> GradedAdverseEvent:
        """Grade and triage a single adverse event input."""
        term_lower = inp.term.lower()
        grade = inp.grade
        rationale = ""

        # 1. Determine grade if not explicitly supplied
        if grade is None or grade == 0:
            if "neutropen" in term_lower and inp.lab_value is not None:
                grade, rationale = CTCAEGradingEngine.grade_anc(inp.lab_value)
            elif "thrombocytopen" in term_lower and inp.lab_value is not None:
                grade, rationale = CTCAEGradingEngine.grade_platelets(inp.lab_value)
            elif "anemia" in term_lower and inp.lab_value is not None:
                grade, rationale = CTCAEGradingEngine.grade_hemoglobin(inp.lab_value)
            elif "alt" in term_lower and inp.lab_value is not None:
                grade, rationale = CTCAEGradingEngine.grade_liver_enzymes(inp.lab_value, enzyme_name="ALT")
            elif "ast" in term_lower and inp.lab_value is not None:
                grade, rationale = CTCAEGradingEngine.grade_liver_enzymes(inp.lab_value, enzyme_name="AST")
            elif "bilirubin" in term_lower and inp.lab_value is not None:
                grade, rationale = CTCAEGradingEngine.grade_bilirubin(inp.lab_value)
            elif "creatinine" in term_lower and inp.lab_value is not None:
                grade, rationale = CTCAEGradingEngine.grade_creatinine(inp.lab_value, inp.baseline_value)
            elif "qtc" in term_lower and inp.lab_value is not None:
                grade, rationale = CTCAEGradingEngine.grade_qtc(inp.lab_value, inp.baseline_value)
            else:
                grade, rationale = CTCAEGradingEngine.grade_clinical_symptom(inp.term, inp.symptoms)
        else:
            rationale = f"Explicitly provided CTCAE Grade {grade} for {inp.term}."

        grade_names = {
            0: "Grade 0 (Normal / None)",
            1: "Grade 1 (Mild)",
            2: "Grade 2 (Moderate)",
            3: "Grade 3 (Severe / Medically Significant)",
            4: "Grade 4 (Life-Threatening)",
            5: "Grade 5 (Death Related to AE)",
        }

        # 2. DLT check
        is_dlt, dlt_reasons = DLTEvaluator.assess_event_dlt(inp, grade)

        # 3. Clinical action triage
        action, guidance, steroid_ind = ClinicalActionEngine.get_management_action(inp, grade, is_dlt)

        is_serious = grade >= 3 or is_dlt or "hospital" in guidance.lower()

        return GradedAdverseEvent(
            term=inp.term,
            system_organ_class=inp.system_organ_class,
            grade=grade,
            grade_name=grade_names.get(grade, f"Grade {grade}"),
            is_serious=is_serious,
            is_dlt=is_dlt,
            dlt_reasons=dlt_reasons,
            management_guidance=guidance,
            action_triage=action.value,
            rationale=rationale,
            details={"steroid_indicated": steroid_ind, "duration_days": inp.duration_days},
        )

    @classmethod
    def triage_patient_encounter(
        cls,
        patient_id: str,
        events: List[AdverseEventInput],
        cycle_number: int = 1,
        alt: Optional[float] = None,
        ast: Optional[float] = None,
        total_bilirubin: Optional[float] = None,
        alk_phosphatase: Optional[float] = None,
    ) -> PatientSafetyReport:
        """Process complete patient encounter dossier."""
        graded_events = [cls.evaluate_single_event(e) for e in events]

        # Grade distribution
        grade_dist: Dict[int, int] = {g: 0 for g in range(6)}
        for ge in graded_events:
            grade_dist[ge.grade] = grade_dist.get(ge.grade, 0) + 1

        highest_grade = max([ge.grade for ge in graded_events], default=0)

        # Hy's law evaluation
        hys_law = DLTEvaluator.evaluate_hys_law(alt, ast, total_bilirubin, alk_phosphatase)

        # Overall DLT compilation
        dlt_events = [ge for ge in graded_events if ge.is_dlt]
        all_dlt_criteria: List[str] = []
        for de in dlt_events:
            all_dlt_criteria.extend(de.dlt_reasons)
        if hys_law and hys_law.meets_hys_law:
            all_dlt_criteria.append("Hy's Law laboratory screening signal triggered")

        is_dlt = len(all_dlt_criteria) > 0
        affected_organs = sorted(list(set(ge.system_organ_class for ge in graded_events if ge.grade >= 2)))

        # Action determination
        dose_mod_needed = is_dlt or highest_grade >= 3
        irae_steroid = any(ge.details.get("steroid_indicated", False) for ge in graded_events)

        if highest_grade >= 4:
            overall_action = ActionTriage.URGENT_HOSPITALIZATION_STAT.value
            overall_rec = "STAT inpatient hospital admission indicated. Permanent study drug discontinuation."
        elif is_dlt or highest_grade == 3:
            overall_action = ActionTriage.HOLD_DOSE.value
            overall_rec = "Dose-Limiting Toxicity (DLT) confirmed. Hold treatment until resolution; resume with dose reduction (-25%)."
        elif highest_grade == 2:
            overall_action = ActionTriage.SUPPORTIVE_CARE.value
            overall_rec = "Grade 2 toxicities present. Optimize outpatient supportive care; monitor weekly."
        else:
            overall_action = ActionTriage.CONTINUE_MONITORING.value
            overall_rec = "No DLT identified. Continue protocol therapy at current dose."

        dlt_assessment = DLTAssessment(
            is_dlt=is_dlt,
            total_dlt_events=len(dlt_events),
            dlt_criteria_met=all_dlt_criteria,
            highest_grade=highest_grade,
            affected_organs=affected_organs,
            clinical_recommendation=overall_rec,
            action_triage=overall_action,
        )

        narrative_parts = [
            f"Patient {patient_id} (Cycle {cycle_number}) presented with {len(events)} adverse event(s).",
            f"Highest CTCAE severity is Grade {highest_grade}.",
        ]
        if is_dlt:
            narrative_parts.append(f"CRITICAL: Dose-Limiting Toxicity (DLT) detected ({'; '.join(all_dlt_criteria)}).")
        else:
            narrative_parts.append("No Dose-Limiting Toxicity criteria met.")
        if hys_law and hys_law.meets_hys_law:
            narrative_parts.append("Hy's Law laboratory screening thresholds are met; clinical causality review is required.")
        if irae_steroid:
            narrative_parts.append("Immune-related AE steroid therapy is indicated.")
        narrative_parts.append(f"Recommendation: {overall_rec}")

        narrative = " ".join(narrative_parts)

        return PatientSafetyReport(
            patient_id=patient_id,
            cycle_number=cycle_number,
            total_events=len(events),
            highest_grade=highest_grade,
            grade_distribution=grade_dist,
            graded_events=graded_events,
            dlt_assessment=dlt_assessment,
            hys_law=hys_law,
            dose_modification_required=dose_mod_needed,
            recommended_action=overall_action,
            irae_steroid_indicated=irae_steroid,
            narrative_summary=narrative,
        )
