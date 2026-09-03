#!/usr/bin/env python3
"""
Command-Line Interface for CTCAE v5.0 Adverse Event Triage & DLT Engine
=======================================================================
Provides interactive and non-interactive workflows for grading adverse events,
evaluating Dose-Limiting Toxicity (DLT), Hy's Law, and irAE management.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from typing import List, Optional

from ctcae_triager import (
    AdverseEventInput,
    CTCAETriageEngine,
    PatientSafetyReport,
)


def format_report_text(rep: PatientSafetyReport) -> str:
    """Format patient report into clinical safety summary."""
    lines = [
        "=" * 80,
        f" CLINICAL TRIAL SAFETY & CTCAE v5.0 TRIAGE REPORT - PATIENT {rep.patient_id} (CYCLE {rep.cycle_number})",
        "=" * 80,
        f"Summary Overview:",
        f"  - Total Adverse Events:       {rep.total_events}",
        f"  - Highest Severity Grade:     Grade {rep.highest_grade}",
        f"  - Grade Distribution:         {rep.grade_distribution}",
        f"  - Dose-Limiting Toxicity:     {'*** POSITIVE (DLT DETECTED) ***' if rep.dlt_assessment.is_dlt else 'NEGATIVE (No DLT)'}",
        f"  - Dose Modification Needed:   {'YES' if rep.dose_modification_required else 'NO'}",
        f"  - irAE Systemic Steroid:      {'INDICATED (High-dose prednisone)' if rep.irae_steroid_indicated else 'Not Indicated'}",
        "-" * 80,
        "Individual Graded Adverse Events:",
    ]
    for idx, e in enumerate(rep.graded_events, 1):
        lines.append(f"  [{idx}] {e.term} (SOC: {e.system_organ_class})")
        lines.append(f"      * Grade:            {e.grade_name}")
        lines.append(f"      * DLT Qualified:    {'YES' if e.is_dlt else 'NO'}")
        if e.dlt_reasons:
            lines.append(f"      * DLT Rationale:    {'; '.join(e.dlt_reasons)}")
        lines.append(f"      * Clinical Action:  {e.action_triage}")
        lines.append(f"      * Management:       {e.management_guidance}")
        lines.append(f"      * Grading Details:  {e.rationale}")

    if rep.hys_law:
        lines.append("-" * 80)
        lines.append("Hy's Law Hepatotoxicity Assessment:")
        lines.append(f"  * Meets Hy's Law:      {'YES - CRITICAL DILI RISK' if rep.hys_law.meets_hys_law else 'No'}")
        lines.append(f"  * ALT/AST Elevation:   {rep.hys_law.alt_ast_elevation_factor}x ULN")
        lines.append(f"  * Bilirubin Elevation: {rep.hys_law.bili_elevation_factor}x ULN")
        lines.append(f"  * Rationale:           {rep.hys_law.rationale}")

    lines.append("=" * 80)
    lines.append(f"PRIMARY ACTION: {rep.recommended_action}")
    lines.append(f"NARRATIVE: {rep.narrative_summary}")
    lines.append("=" * 80)
    return "\n".join(lines)


def run_demo(as_json: bool = False) -> int:
    """Run standard clinical vignettes."""
    vignettes = [
        {
            "id": "PT-101-DLT-FEBNEUT",
            "cycle": 1,
            "events": [
                AdverseEventInput(
                    term="Neutropenia", system_organ_class="Blood and lymphatic system disorders",
                    lab_value=420.0, temperature_c=38.6, duration_days=3
                ),
                AdverseEventInput(term="Fever", symptoms=["temperature 38.6C", "chills"]),
            ],
            "alt": 28.0, "ast": 32.0, "bili": 0.8,
        },
        {
            "id": "PT-102-IRAE-COLITIS",
            "cycle": 2,
            "events": [
                AdverseEventInput(
                    term="Colitis", system_organ_class="Gastrointestinal disorders",
                    symptoms=["7 or more stools per day", "incontinence", "severe abdominal cramping"],
                    is_immune_mediated=True, duration_days=5
                )
            ],
            "alt": 35.0, "ast": 40.0, "bili": 0.7,
        },
        {
            "id": "PT-103-HYS-LAW-DILI",
            "cycle": 1,
            "events": [
                AdverseEventInput(term="ALT increased", lab_value=240.0), # 6x ULN
                AdverseEventInput(term="AST increased", lab_value=195.0), # ~5x ULN
                AdverseEventInput(term="Blood bilirubin increased", lab_value=3.2), # ~2.6x ULN
            ],
            "alt": 240.0, "ast": 195.0, "bili": 3.2, "alk": 110.0,
        },
        {
            "id": "PT-104-ROUTINE-GRADE1",
            "cycle": 3,
            "events": [
                AdverseEventInput(term="Fatigue", symptoms=["mild tiredness not interfering with ADL"]),
                AdverseEventInput(term="Nausea", symptoms=["mild loss of appetite without vomiting"]),
            ],
            "alt": 30.0, "ast": 25.0, "bili": 0.6,
        },
    ]

    reports = []
    for v in vignettes:
        rep = CTCAETriageEngine.triage_patient_encounter(
            patient_id=v["id"],
            events=v["events"],
            cycle_number=v["cycle"],
            alt=v.get("alt"),
            ast=v.get("ast"),
            total_bilirubin=v.get("bili"),
            alk_phosphatase=v.get("alk"),
        )
        reports.append(rep)

    if as_json:
        print(json.dumps([r.to_dict() for r in reports], indent=2))
        return 0

    print("=" * 80)
    print(" CTCAE v5.0 ADVERSE EVENT TRIAGE & DLT BENCHMARK VIGNETTES")
    print("=" * 80)
    for rep in reports:
        print(format_report_text(rep))
        print()
    return 0


def run_interactive() -> int:
    """Interactive CLI triage wizard."""
    print("=" * 70)
    print(" CTCAE v5.0 Adverse Event Triage & Safety Studio")
    print("=" * 70)
    print("1. Quick Grade Single Lab / Adverse Event (ANC, Platelets, LFTs, QTc, etc.)")
    print("2. Triage Multi-Event Patient Encounter")
    print("3. Run Benchmark Clinical Vignettes Demo")
    print("q. Exit")
    print("-" * 70)

    choice = input("Select an option [1-3, q]: ").strip()
    if choice in ("q", "quit", "exit"):
        return 0

    if choice == "1":
        term = input("Adverse Event Term (e.g. Neutropenia, ALT, Diarrhea, QTc): ").strip() or "Neutropenia"
        val_str = input("Laboratory Value (optional, press Enter to skip): ").strip()
        lab_val = float(val_str) if val_str else None
        sym_str = input("Symptoms / Description (optional, e.g. 'hospitalization', 'limiting self care'): ").strip()
        syms = [sym_str] if sym_str else []
        is_imm = input("Is immune-mediated / irAE? [y/N]: ").strip().lower() == "y"

        inp = AdverseEventInput(term=term, lab_value=lab_val, symptoms=syms, is_immune_mediated=is_imm)
        graded = CTCAETriageEngine.evaluate_single_event(inp)
        print("\n" + "=" * 60)
        print(f" RESULT FOR: {graded.term}")
        print("=" * 60)
        print(f"  - CTCAE v5.0 Grade: {graded.grade_name}")
        print(f"  - DLT Qualifier:    {'YES (DLT)' if graded.is_dlt else 'NO'}")
        print(f"  - Action Triage:    {graded.action_triage}")
        print(f"  - Guidance:         {graded.management_guidance}")
        print(f"  - Rationale:        {graded.rationale}")
        print("=" * 60)

    elif choice == "2":
        pid = input("Patient ID [PT-901]: ").strip() or "PT-901"
        cycle = int(input("Cycle Number [1]: ").strip() or "1")
        print("Enter events (empty line when finished):")
        events = []
        while True:
            term = input("  Event Term (press Enter to finish): ").strip()
            if not term:
                break
            val_str = input("    Lab Value (or Enter if clinical symptom): ").strip()
            lab_val = float(val_str) if val_str else None
            sym = input("    Clinical description / symptoms: ").strip()
            events.append(AdverseEventInput(term=term, lab_value=lab_val, symptoms=[sym] if sym else []))

        if not events:
            events.append(AdverseEventInput(term="Fatigue", symptoms=["mild"]))

        rep = CTCAETriageEngine.triage_patient_encounter(pid, events, cycle)
        print(format_report_text(rep))

    elif choice == "3":
        run_demo()

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctcae_triage",
        description="CTCAE v5.0 Adverse Event Triage & Dose-Limiting Toxicity (DLT) Engine",
    )
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive studio")
    parser.add_argument("--demo", action="store_true", help="Run benchmark clinical vignettes")
    parser.add_argument("--json", action="store_true", help="Output results in JSON")

    sub = parser.add_subparsers(dest="command", help="Subcommands")

    # Evaluate single event
    ev_p = sub.add_parser("evaluate", help="Evaluate and grade a single adverse event")
    ev_p.add_argument("--term", required=True, help="Adverse event term (e.g. Neutropenia, ALT, Diarrhea)")
    ev_p.add_argument("--lab-value", type=float, default=None, help="Laboratory value")
    ev_p.add_argument("--baseline", type=float, default=None, help="Baseline lab value")
    ev_p.add_argument("--symptoms", nargs="*", default=[], help="Symptom keywords")
    ev_p.add_argument("--duration", type=int, default=1, help="Duration in days")
    ev_p.add_argument("--temp", type=float, default=None, help="Body temperature in Celsius")
    ev_p.add_argument("--bleeding", action="store_true", help="Associated with bleeding")
    ev_p.add_argument("--immune-mediated", action="store_true", help="Is immune-related AE (irAE)")
    ev_p.add_argument("--json", action="store_true", help="Output results in JSON")

    # Triage patient
    pt_p = sub.add_parser("triage", help="Triage complete patient encounter JSON")
    pt_p.add_argument("--patient-id", default="PT-001", help="Patient identifier")
    pt_p.add_argument("--cycle", type=int, default=1, help="Treatment cycle number")
    pt_p.add_argument("--payload", help="JSON string or file path containing event array")
    pt_p.add_argument("--alt", type=float, default=None, help="ALT (U/L)")
    pt_p.add_argument("--ast", type=float, default=None, help="AST (U/L)")
    pt_p.add_argument("--bili", type=float, default=None, help="Total Bilirubin (mg/dL)")
    pt_p.add_argument("--alk", type=float, default=None, help="Alkaline Phosphatase (U/L)")
    pt_p.add_argument("--json", action="store_true", help="Output results in JSON")

    # Batch CSV
    b_p = sub.add_parser("batch", help="Process adverse events CSV cohort")
    b_p.add_argument("--input", "-in", required=True, help="Input CSV path")
    b_p.add_argument("--output", "-out", required=True, help="Output CSV path")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.interactive or (not args.command and not args.demo):
        if not args.demo and (argv is None or len(argv) == 0):
            return run_interactive()

    if args.demo:
        return run_demo(as_json=args.json)

    if args.command == "evaluate":
        inp = AdverseEventInput(
            term=args.term,
            lab_value=args.lab_value,
            baseline_value=args.baseline,
            symptoms=args.symptoms,
            duration_days=args.duration,
            temperature_c=args.temp,
            has_bleeding=args.bleeding,
            is_immune_mediated=args.immune_mediated,
        )
        graded = CTCAETriageEngine.evaluate_single_event(inp)
        if args.json:
            print(json.dumps(asdict(graded), indent=2))
        else:
            print("=" * 60)
            print(f" CTCAE v5.0 EVALUATION: {graded.term}")
            print("=" * 60)
            print(f"  - Severity:       {graded.grade_name}")
            print(f"  - DLT Status:     {'YES (DLT QUALIFIED)' if graded.is_dlt else 'NO'}")
            if graded.dlt_reasons:
                print(f"  - DLT Reasons:    {'; '.join(graded.dlt_reasons)}")
            print(f"  - Action Triage:  {graded.action_triage}")
            print(f"  - Guidance:       {graded.management_guidance}")
            print(f"  - Rationale:      {graded.rationale}")
            print("=" * 60)
        return 0

    if args.command == "triage":
        events = []
        if args.payload:
            try:
                if args.payload.endswith(".json"):
                    with open(args.payload, "r") as f:
                        data = json.load(f)
                else:
                    data = json.loads(args.payload)
                if isinstance(data, list):
                    for d in data:
                        events.append(AdverseEventInput(**d))
            except Exception as e:
                print(f"Error parsing payload: {e}", file=sys.stderr)
                return 1
        if not events:
            events.append(AdverseEventInput(term="Fatigue", symptoms=["Grade 1 mild"]))

        rep = CTCAETriageEngine.triage_patient_encounter(
            patient_id=args.patient_id,
            events=events,
            cycle_number=args.cycle,
            alt=args.alt,
            ast=args.ast,
            total_bilirubin=args.bili,
            alk_phosphatase=args.alk,
        )
        if args.json:
            print(rep.to_json())
        else:
            print(format_report_text(rep))
        return 0

    if args.command == "batch":
        try:
            with open(args.input, "r", newline="", encoding="utf-8-sig") as f_in:
                reader = csv.DictReader(f_in)
                rows = list(reader)
            out_rows = []
            for r in rows:
                val = float(r["lab_value"]) if r.get("lab_value") else None
                dur = int(r["duration_days"]) if r.get("duration_days") else 1
                imm = r.get("is_immune_mediated", "false").lower() in ("true", "1", "yes")
                inp = AdverseEventInput(
                    term=r.get("term", "Adverse Event"),
                    system_organ_class=r.get("system_organ_class", "General disorders"),
                    lab_value=val,
                    symptoms=[r.get("symptoms", "")],
                    duration_days=dur,
                    is_immune_mediated=imm,
                )
                graded = CTCAETriageEngine.evaluate_single_event(inp)
                out_rows.append({
                    "patient_id": r.get("patient_id", "PT-UNKNOWN"),
                    "term": graded.term,
                    "grade": graded.grade,
                    "grade_name": graded.grade_name,
                    "is_dlt": graded.is_dlt,
                    "action_triage": graded.action_triage,
                    "management_guidance": graded.management_guidance,
                })
            with open(args.output, "w", newline="", encoding="utf-8") as f_out:
                if out_rows:
                    writer = csv.DictWriter(f_out, fieldnames=list(out_rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(out_rows)
            print(f"Successfully triaged {len(out_rows)} events to {args.output}")
            return 0
        except Exception as e:
            print(f"Batch error: {e}", file=sys.stderr)
            return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
