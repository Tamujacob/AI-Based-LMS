"""
scripts/test_training_data.py
─────────────────────────────
Run this to verify the training data JSON loads correctly
and is ready to be used by model_trainer.py

Usage:
    python scripts/test_training_data.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_training_data(path: str) -> dict:
    """Load and validate the training data JSON."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"\n  File not found: {path}"
            f"\n  Make sure you copied training_data_200.json to data/training/"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_record(record: dict, idx: int) -> list:
    """Check a single record has all required fields. Returns list of errors."""
    errors = []
    required_top = ["record_id", "loan_id", "client", "loan",
                    "borrower_history", "repayments",
                    "repayment_summary", "ai_assessment"]
    for field in required_top:
        if field not in record:
            errors.append(f"Record {idx}: missing top-level field '{field}'")

    if "client" in record:
        for f in ["occupation", "monthly_income_ugx", "district"]:
            if f not in record["client"]:
                errors.append(f"Record {idx}: client missing '{f}'")

    if "loan" in record:
        for f in ["principal_amount", "duration_months", "loan_type", "status"]:
            if f not in record["loan"]:
                errors.append(f"Record {idx}: loan missing '{f}'")

    if "ai_assessment" in record:
        label = record["ai_assessment"].get("risk_label")
        if label not in ("LOW", "MEDIUM", "HIGH"):
            errors.append(
                f"Record {idx}: invalid risk_label '{label}' "
                f"(expected LOW, MEDIUM, or HIGH)"
            )

    return errors


def extract_features(record: dict) -> dict:
    """
    Extract the 12 features the model_trainer will use.
    This is a preview of what the ML model will see.
    """
    client  = record["client"]
    loan    = record["loan"]
    history = record["borrower_history"]
    summary = record["repayment_summary"]

    income  = client.get("monthly_income_ugx", 500000) or 500000
    principal = loan["principal_amount"]
    duration  = loan["duration_months"]

    return {
        "principal_amount":        principal,
        "duration_months":         duration,
        "income_to_loan_ratio":    round(principal / (income * duration), 4),
        "monthly_income_ugx":      income,
        "loan_type":               loan["loan_type"],
        "occupation":              client["occupation"],
        "district":                client["district"],
        "previous_loans":          history["previous_loans_count"],
        "previous_defaults":       history["previous_defaults"],
        "previous_completed":      history["previous_completed"],
        "payment_consistency":     summary["payment_consistency_score"],
        "days_overdue":            summary["days_overdue"],
        # Target label
        "risk_label":              record["ai_assessment"]["risk_label"],
    }


def main():
    from app.config.settings import TRAINING_DATA_PATH

    print("\n" + "="*55)
    print("  Bingongold Credit — Training Data Validation")
    print("="*55)

    # ── Load ─────────────────────────────────────────────────
    print(f"\n  Loading: {TRAINING_DATA_PATH}")
    try:
        data = load_training_data(TRAINING_DATA_PATH)
    except FileNotFoundError as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)

    records = data.get("records", [])
    meta    = data.get("metadata", {})

    print(f"  Records loaded:  {len(records)}")
    print(f"  Dataset:         {meta.get('dataset_name', '—')}")
    print(f"  Generated:       {meta.get('generated_date', '—')}")

    # ── Validate ──────────────────────────────────────────────
    print(f"\n  Validating all {len(records)} records...")
    all_errors = []
    for i, rec in enumerate(records, 1):
        errs = validate_record(rec, i)
        all_errors.extend(errs)

    if all_errors:
        print(f"\n  VALIDATION ERRORS ({len(all_errors)}):")
        for e in all_errors[:10]:
            print(f"    - {e}")
        if len(all_errors) > 10:
            print(f"    ... and {len(all_errors)-10} more")
    else:
        print("  All records valid ✓")

    # ── Risk distribution ─────────────────────────────────────
    labels = [r["ai_assessment"]["risk_label"] for r in records]
    low    = labels.count("LOW")
    med    = labels.count("MEDIUM")
    high   = labels.count("HIGH")

    print(f"\n  Risk Label Distribution:")
    print(f"    LOW    : {low:>3} records  ({low/len(records)*100:.0f}%)")
    print(f"    MEDIUM : {med:>3} records  ({med/len(records)*100:.0f}%)")
    print(f"    HIGH   : {high:>3} records  ({high/len(records)*100:.0f}%)")

    # ── Feature extraction preview ────────────────────────────
    print(f"\n  Feature Extraction Preview (first 3 records):")
    print(f"  {'Loan ID':<18} {'Principal':>12} {'Duration':>9} "
          f"{'Inc/Loan':>9} {'Occ':<22} {'Risk':<8}")
    print(f"  {'-'*80}")

    for rec in records[:3]:
        feat = extract_features(rec)
        occ  = feat["occupation"][:20]
        print(f"  {rec['loan_id']:<18} "
              f"UGX {feat['principal_amount']:>8,.0f} "
              f"{feat['duration_months']:>6}m  "
              f"{feat['income_to_loan_ratio']:>8.2f}  "
              f"{occ:<22} "
              f"{feat['risk_label']:<8}")

    # ── Loan type distribution ────────────────────────────────
    loan_types = {}
    for rec in records:
        lt = rec["loan"]["loan_type"]
        loan_types[lt] = loan_types.get(lt, 0) + 1

    print(f"\n  Loan Type Distribution:")
    for lt, count in sorted(loan_types.items(), key=lambda x: -x[1]):
        print(f"    {lt:<30} : {count}")

    # ── Status distribution ───────────────────────────────────
    statuses = {}
    for rec in records:
        s = rec["loan"]["status"]
        statuses[s] = statuses.get(s, 0) + 1

    print(f"\n  Loan Status Distribution:")
    for s, count in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"    {s:<15} : {count}")

    # ── Occupation distribution ───────────────────────────────
    occs = {}
    for rec in records:
        o = rec["client"]["occupation"]
        occs[o] = occs.get(o, 0) + 1
    top_occs = sorted(occs.items(), key=lambda x: -x[1])[:6]

    print(f"\n  Top 6 Occupations in Dataset:")
    for o, count in top_occs:
        print(f"    {o:<28} : {count}")

    # ── Ready check ───────────────────────────────────────────
    print(f"\n  {'='*55}")
    if not all_errors and len(records) == 200:
        print(f"  ✓  Training data is READY for model_trainer.py")
        print(f"  ✓  Run:  python scripts/train_model.py")
    else:
        print(f"  ✗  Fix the errors above before training")
    print(f"  {'='*55}\n")


if __name__ == "__main__":
    main()