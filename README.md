# Adverse Event CTCAE v5.0 Triage & Dose-Limiting Toxicity Engine

A clinical-grade, zero-dependency Python implementation of the National Cancer Institute (NCI) **Common Terminology Criteria for Adverse Events (CTCAE) Version 5.0**, designed for phase I/II oncology clinical trials, drug safety pharmacovigilance, Dose-Limiting Toxicity (DLT) adjudication, Hy's Law Drug-Induced Liver Injury (DILI) screening, and Immune-Related Adverse Event (irAE) management.

---

## Core Capabilities

- **Deterministic CTCAE v5.0 Grading**:
  - **Hematology**: Absolute Neutrophil Count (ANC), Platelets, Hemoglobin, Leukocytes, Lymphocytes.
  - **Hepatic**: ALT, AST, Total Bilirubin, Alkaline Phosphatase with exact $x\text{ ULN}$ threshold cutoffs.
  - **Renal**: Serum Creatinine (fold baseline / ULN) and acute kidney injury staging.
  - **Electrolytes & Cardiac**: QTc prolongation (Fridericia / Bazett ms cutoffs and $\Delta\text{QTc} > 60\text{ ms}$ delta), Hyponatremia, Hyperkalemia.
  - **Symptom NLP Matching**: Qualitative grading for diarrhea (stool count/day), nausea/vomiting, rash BSA %, peripheral neuropathy, pneumonitis, and Cytokine Release Syndrome (CRS).

- **Oncology Phase I/II Dose-Limiting Toxicity (DLT) Engine**:
  - Evaluation according to standard 3+3 design and Bayesian Optimal Interval (BOIN) protocols:
    - Febrile neutropenia ($\text{ANC} < 1000/\text{mm}^3 + \text{temp} \ge 38.0^\circ\text{C}$).
    - Grade 4 neutropenia persisting $\ge 5\text{ days}$.
    - Grade 4 thrombocytopenia or Grade 3 thrombocytopenia with clinically significant bleeding.
    - Grade $\ge 3$ non-hematologic toxicities (excluding transient nausea/alopecia).
    - Unresolved toxicity causing dose delay $> 14\text{ days}$.
    - Any Grade 5 toxicity (death related to adverse event).

- **Hy's Law DILI Screening (FDA / Zimmerman Criteria)**:
  - $\text{ALT or AST} \ge 3\times\text{ULN}$
  - $\text{Total Bilirubin} \ge 2\times\text{ULN}$
  - $\text{Alkaline Phosphatase} < 2\times\text{ULN}$ (differentiating hepatocellular injury from cholestasis).

- **ASCO/NCCN Immune-Related Adverse Event (irAE) Triage**:
  - Systemic corticosteroid guidance ($0.5-2.0\text{ mg/kg/day}$ prednisone equivalent).
  - Treatment hold vs. permanent discontinuation triage.

---

## CLI Usage

### 1. Interactive Safety Studio
```bash
python cli.py
# or
python cli.py --interactive
```

### 2. Run Benchmark Clinical Vignettes Demo
```bash
python cli.py --demo
```

### 3. Evaluate an Individual Adverse Event
```bash
python cli.py evaluate --term "Neutropenia" --lab-value 420 --duration 6 --temp 38.4
```

### 4. Triage Complete Patient Dossier
```bash
python cli.py triage --patient-id "PT-042" --cycle 1 --alt 250 --ast 210 --bili 3.5 --alk 95
```

### 5. Batch Cohort Processing via CSV
```bash
python cli.py batch --input patient_adverse_events.csv --output triaged_safety_report.csv
```

---

## Python API Example

```python
from ctcae_triager import (
    AdverseEventInput,
    CTCAETriageEngine,
)

events = [
    AdverseEventInput(
        term="Neutropenia",
        lab_value=450.0, # Grade 4
        temperature_c=38.6,
        duration_days=4,
    ),
    AdverseEventInput(
        term="Colitis",
        symptoms=[">=7 stools per day", "hospitalization indicated"],
        is_immune_mediated=True,
    ),
]

report = CTCAETriageEngine.triage_patient_encounter(
    patient_id="PT-202",
    events=events,
    cycle_number=1,
)

print(f"Highest Severity: Grade {report.highest_grade}")
print(f"DLT Identified: {report.dlt_assessment.is_dlt}")
print(f"Recommended Action: {report.recommended_action}")
print(f"irAE Steroid Indicated: {report.irae_steroid_indicated}")
```

---

## Unit Testing

Run the full 29-case test suite:

```bash
python -m unittest test_ctcae_triager.py
```

---

## License

MIT License. Designed for clinical research organizations (CRO), biostatisticians, and clinical trial safety review committees.
