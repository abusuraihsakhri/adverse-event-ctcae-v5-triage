# CTCAE v5.0 Adverse Event Triage & Dose-Limiting Toxicity (DLT) Engine

A Python clinical oncology safety evaluation library and CLI tool implementing the National Cancer Institute (NCI) Common Terminology Criteria for Adverse Events (CTCAE) version 5.0, protocol-defined Dose-Limiting Toxicity (DLT) rules for Phase I/II oncology trials, Hy's Law drug-induced liver injury (DILI) screening, and ASCO/NCCN immune-related adverse event (irAE) corticosteroid triage.

Requires Python standard library only (zero external runtime dependencies).

---

## Features

- **NCI CTCAE v5.0 Numerical & Symptom Grading:**
  - **Hematologic Toxicity:** Absolute Neutrophil Count (ANC / neutropenia), Platelets (thrombocytopenia), Hemoglobin (anemia).
  - **Hepatic & Metabolic:** ALT, AST, Total Bilirubin, Alkaline Phosphatase.
  - **Renal & Electrolytes:** Serum Creatinine, AKI stages, baseline ratio shifts.
  - **Cardiac Safety:** Fridericia/Bazett corrected QTc interval prolongation ($\ge 501\text{ ms}$, $\Delta \ge 60\text{ ms}$).
  - **Clinical Symptoms:** Gastrointestinal (diarrhea, colitis, nausea, vomiting), neurological, dermatological, and pulmonary toxicities.
- **Phase I/II Dose-Limiting Toxicity (DLT) Criteria:**
  - Grade 4 persistent neutropenia ($\ge 5\text{ days}$).
  - Febrile neutropenia (ANC $< 1000/\text{mm}^3$ + fever $\ge 38.0^\circ\text{C}$).
  - Grade 4 thrombocytopenia or Grade 3 with clinically significant bleeding.
  - Grade $\ge 3$ non-hematologic toxicities (excluding protocol exceptions).
  - Treatment delays $> 14\text{ days}$ due to unresolved drug-related toxicity.
  - Grade 5 fatalities.
- **Hy's Law Hepatotoxicity Screening:**
  - Transaminases (ALT or AST) $\ge 3\times\text{ULN}$ + Total Bilirubin $\ge 2\times\text{ULN}$ with Alkaline Phosphatase $< 2\times\text{ULN}$.
- **Immune-Related AE (irAE) Triage:**
  - ASCO/NCCN guideline-directed corticosteroid initiation (0.5–1.0 mg/kg vs. 1.0–2.0 mg/kg prednisone equivalent) and taper schedules.
- **Actionable Dose Modifications:** Guidance for dose holds, level -1 (-25%), level -2 (-50%) dose reductions, and permanent discontinuations.
- **Batch CSV Processing:** High-throughput safety cohort triage and surveillance.

---

## Installation & Requirements

- Python 3.10+ (tested on 3.10, 3.11, 3.12)
- Zero external runtime dependencies. `pytest` is optional for running tests.

```bash
git clone https://github.com/abusuraihsakhri/adverse-event-ctcae-v5-triage.git
cd adverse-event-ctcae-v5-triage
```

---

## CLI Usage

### 1. Evaluate Single Adverse Event
Evaluate laboratory finding:
```bash
python cli.py evaluate --term Neutropenia --lab-value 450
```
Output as JSON:
```bash
python cli.py evaluate --term Neutropenia --lab-value 450 --json
```

Evaluate symptom with clinical descriptors:
```bash
python cli.py evaluate --term Colitis --symptoms ">=7 stools per day severe pain" --duration 4 --immune-mediated
```

### 2. Triage Complete Patient Encounter
```bash
python cli.py triage --patient-id PT-101 --cycle 1 --alt 240 --ast 195 --bili 3.2 --alk 110 --json
```

### 3. Run Benchmark Clinical Vignettes
```bash
python cli.py --demo
```

### 4. Batch CSV Triage
```bash
python cli.py batch --input sample.csv --output results.csv
```

---

## Python API Quickstart

```python
from ctcae_triager import AdverseEventInput, CTCAETriageEngine

# 1. Evaluate individual clinical event
event = AdverseEventInput(
    term="Neutropenia",
    system_organ_class="Blood and lymphatic system disorders",
    lab_value=450.0,
    duration_days=6,
)
graded = CTCAETriageEngine.evaluate_single_event(event)
print(f"Grade: {graded.grade_name} | DLT: {graded.is_dlt} | Action: {graded.action_triage}")

# 2. Triage patient encounter with hepatic labs
report = CTCAETriageEngine.triage_patient_encounter(
    patient_id="PT-901",
    events=[event],
    cycle_number=1,
    alt=180.0,
    total_bilirubin=2.8,
    alk_phosphatase=95.0,
)
print(f"DLT Status: {report.dlt_assessment.is_dlt}")
print(f"Hy's Law Met: {report.hys_law.meets_hys_law if report.hys_law else False}")
print(f"Action: {report.recommended_action}")
```

---

## Running Tests

Run the test suite using standard `unittest` or `pytest`:

```bash
python test_ctcae_triager.py
# or
pytest -v
```

## Security & Input Validation

The engine includes defensive guards against common vulnerabilities:

- **Input validation:** `AdverseEventInput` validates term non-emptiness, lab values are finite/non-negative, and temperature is physiologically plausible (30–45 °C).
- **Division-by-zero protection:** Grading functions reject zero/negative ULN reference values.
- **Path traversal protection:** The CLI `batch` and `triage --payload` commands resolve file paths safely using `ctcae_triager.safe_resolve_path`.
- **Zero external runtime dependencies:** No third-party packages required, reducing supply-chain attack surface.

