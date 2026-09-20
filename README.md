# CTCAE v5.0 Adverse Event Triage

### [Open the Live Application →](https://abusuraihsakhri.github.io/adverse-event-ctcae-v5-triage/)

Python 3.10+ utilities for selected NCI CTCAE v5.0 grading thresholds, adverse-event screening, protocol-style dose-limiting toxicity (DLT) checks, Hy's Law laboratory signal screening, and explicitly identified immune-related adverse events (irAEs).

The project provides a Python API, command-line interface, batch CSV workflow, and a browser interface that runs the same Python engine client-side with Pyodide.

> **Scope:** This is a research and educational utility, not a complete CTCAE dictionary, validated clinical decision-support system, trial protocol, or substitute for clinician review. DLT definitions are protocol-specific. Confirm all grading and management decisions against the official CTCAE, the active protocol, product labeling, and applicable clinical guidance.

## Features

- Selected laboratory grading for ANC, platelets, hemoglobin, ALT/AST, bilirubin, creatinine, and QTc.
- Symptom-severity heuristics based on supplied clinical descriptors.
- Default Phase I/II-style DLT screening rules with event-level rationale.
- Hy's Law **laboratory** signal screening using transaminase, bilirubin, and alkaline-phosphatase thresholds. The engine does not establish drug causality or exclude alternative etiologies.
- irAE management prompts only when the caller explicitly marks an event as immune-mediated.
- Single-event, encounter, JSON, and CSV command-line workflows.
- Static browser UI with light/dark themes; Python executes in the browser through Pyodide.
- Standard-library-only Python runtime dependencies.

## Installation

Clone the repository and install it locally:

```bash
git clone https://github.com/abusuraihsakhri/adverse-event-ctcae-v5-triage.git
cd adverse-event-ctcae-v5-triage
python -m pip install .
```

The installed command is:

```bash
adverse-event-ctcae-v5-triage --help
```

You can also run the repository CLI directly with `python cli.py`.

## CLI examples

Grade one event:

```bash
adverse-event-ctcae-v5-triage evaluate \
  --term Neutropenia \
  --lab-value 450 \
  --duration 6 \
  --json
```

Triage an encounter from an inline JSON event array:

```bash
adverse-event-ctcae-v5-triage triage \
  --patient-id PT-001 \
  --payload '[{"term":"Nausea","symptoms":["mild"]}]' \
  --json
```

Run the liver laboratory screen alongside an encounter:

```bash
adverse-event-ctcae-v5-triage triage \
  --patient-id PT-002 \
  --alt 200 \
  --ast 180 \
  --bili 3.0 \
  --alk 90 \
  --json
```

Process a CSV cohort:

```bash
adverse-event-ctcae-v5-triage batch --input sample.csv --output results.csv
```

## Python API

```python
from ctcae_triager import AdverseEventInput, CTCAETriageEngine

event = AdverseEventInput(
    term="Neutropenia",
    system_organ_class="Blood and lymphatic system disorders",
    lab_value=450.0,
    duration_days=6,
)

graded = CTCAETriageEngine.evaluate_single_event(event)

print(graded.grade_name)
print(graded.is_dlt)
print(graded.action_triage)
```

For laboratory thresholds that depend on the local reference range, call the relevant grading function directly and provide the applicable ULN/baseline rather than assuming the included defaults.

## Browser application

The static browser interface is in `web/`. GitHub Pages builds it with the current `ctcae_triager/__init__.py` engine and runs that Python code in a Web Worker through Pyodide. This avoids a separate JavaScript reimplementation of the grading logic.

The first browser load downloads the Pyodide WebAssembly runtime from jsDelivr. Subsequent loads can use the browser cache. A current WebAssembly-capable browser is recommended.

## Privacy and data handling

The Python CLI processes local inputs locally.

The browser application does not send adverse-event inputs to this repository or a backend service. Analysis runs in the browser. The page loads the Pyodide runtime from jsDelivr, and it may store only the light/dark theme preference in browser local storage. No patient identifiers are required by the browser form.

The CLI accepts user-selected input and output paths. `safe_resolve_path()` normalizes and validates file paths when requested, but it is **not** a filesystem sandbox and intentionally allows paths outside the repository.

## Development and testing

Install the test/build tools:

```bash
python -m pip install pytest build
```

Run the test suite and build:

```bash
pytest -q
python -m build
```

CI tests Python 3.10 through 3.14, compiles the source, validates the browser JavaScript syntax, builds wheel/sdist artifacts, installs the wheel, and smoke-tests the installed console command.

Synthetic regression examples are stored in `benchmark_dataset.json`. They are software test fixtures, not a clinical validation dataset.

## Technology

- Python standard library
- `setuptools` packaging
- `pytest` for tests
- HTML/CSS/JavaScript for the browser interface
- Pyodide/WebAssembly for client-side Python
- GitHub Actions for CI and GitHub Pages deployment

## References

- NCI, **Common Terminology Criteria for Adverse Events (CTCAE) v5.0**, published November 27, 2017: https://dctd.cancer.gov/research/ctep-trials/for-sites/adverse-events
- U.S. FDA, **Drug-Induced Liver Injury: Premarketing Clinical Evaluation**: https://www.fda.gov/media/116737/download
- Schneider BJ, et al. **Management of Immune-Related Adverse Events in Patients Treated With Immune Checkpoint Inhibitor Therapy: ASCO Guideline Update.** *J Clin Oncol.* 2021;39(36):4073-4126. https://doi.org/10.1200/JCO.21.01440
- Pyodide documentation: https://pyodide.org/en/stable/

## License

MIT. See [LICENSE](LICENSE).
