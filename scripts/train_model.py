"""
scripts/train_model.py
──────────────────────────────────────────────────────────────
Trains the offline risk scoring model from the 200-record
training JSON and saves it to models/risk_model.pkl

Run:
    python scripts/train_model.py
"""

import sys
import os
import json
import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("\n" + "="*55)
    print("  Bingongold Credit — Model Trainer")
    print("="*55)

    # ── Load training data ─────────────────────────────────────────────
    from app.config.settings import TRAINING_DATA_PATH
    print(f"\n  Loading: {TRAINING_DATA_PATH}")

    if not os.path.exists(TRAINING_DATA_PATH):
        print(f"\n  ERROR: File not found: {TRAINING_DATA_PATH}")
        sys.exit(1)

    with open(TRAINING_DATA_PATH, "r") as f:
        data = json.load(f)

    records = data["records"]
    print(f"  Records loaded: {len(records)}")

    # ── Extract features ───────────────────────────────────────────────
    OCCUPATION_MAP = {
        "Teacher": 3, "Nurse": 3, "Civil Servant": 3, "Accountant": 3,
        "Police Officer": 3, "Doctor": 3,
        "Small Business Owner": 2, "Driver": 2, "Mechanic": 2,
        "Carpenter": 2, "Mason": 2, "Tailor": 2, "Electrician": 2,
        "Plumber": 2, "Cook": 2, "Salon Operator": 2, "Shopkeeper": 2,
        "Security Guard": 1, "Boda Boda Rider": 1, "Market Vendor": 1,
        "Farmer": 1, "Hawker": 1, "Cleaner": 1,
    }

    X, y = [], []
    for r in records:
        client  = r["client"]
        loan    = r["loan"]
        history = r["borrower_history"]
        summary = r["repayment_summary"]

        income    = client.get("monthly_income_ugx", 500000) or 500000
        principal = loan["principal_amount"]
        duration  = loan["duration_months"]

        features = [
            principal,
            duration,
            round(principal / (income * duration), 4),
            income,
            ["Business Loan","School Fees Loan","Tax Clearance Loan",
             "Development Loan","Asset Acquisition Loan"].index(
                loan["loan_type"]) if loan["loan_type"] in
            ["Business Loan","School Fees Loan","Tax Clearance Loan",
             "Development Loan","Asset Acquisition Loan"] else 0,
            OCCUPATION_MAP.get(client["occupation"], 2),
            history["previous_loans_count"],
            history["previous_defaults"],
            history["previous_completed"],
            summary["payment_consistency_score"],
            summary["days_overdue"],
            1 if history["is_repeat_borrower"] else 0,
        ]
        X.append(features)

        label_map = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        y.append(label_map[r["ai_assessment"]["risk_label"]])

    X = np.array(X)
    y = np.array(y)
    print(f"  Features extracted: {X.shape[0]} rows × {X.shape[1]} columns")

    # ── Train model ────────────────────────────────────────────────────
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline

    print("\n  Training RandomForestClassifier...")

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model",  RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            random_state=42,
            class_weight="balanced",
        ))
    ])

    # Cross-validation score
    scores = cross_val_score(pipeline, X, y, cv=5, scoring="accuracy")
    print(f"  Cross-validation accuracy: {scores.mean():.1%} ± {scores.std():.1%}")

    # Train on full dataset
    pipeline.fit(X, y)

    # ── Save model ─────────────────────────────────────────────────────
    os.makedirs("models", exist_ok=True)
    model_path   = "models/risk_model.pkl"
    feature_path = "models/feature_info.json"

    joblib.dump(pipeline, model_path)

    feature_info = {
        "feature_names": [
            "principal_amount", "duration_months", "income_to_loan_ratio",
            "monthly_income", "loan_type_encoded", "occupation_stability",
            "previous_loans", "previous_defaults", "previous_completed",
            "payment_consistency", "days_overdue", "is_repeat_borrower"
        ],
        "label_map":     {"0": "LOW", "1": "MEDIUM", "2": "HIGH"},
        "occupation_map": OCCUPATION_MAP,
        "loan_types": ["Business Loan","School Fees Loan","Tax Clearance Loan",
                       "Development Loan","Asset Acquisition Loan"],
        "training_records": len(records),
        "cv_accuracy": round(float(scores.mean()), 4),
    }
    with open(feature_path, "w") as f:
        json.dump(feature_info, f, indent=2)

    print(f"\n  Model saved:   {model_path}")
    print(f"  Feature info:  {feature_path}")

    # ── Distribution check ─────────────────────────────────────────────
    preds = pipeline.predict(X)
    label_names = ["LOW", "MEDIUM", "HIGH"]
    print("\n  Training set predictions:")
    for i, name in enumerate(label_names):
        count = (preds == i).sum()
        print(f"    {name:<8}: {count}")

    print("\n  " + "="*53)
    print("  ✓  Model trained and saved successfully")
    print("  ✓  The app will now use this model for offline scoring")
    print("  " + "="*53 + "\n")

if __name__ == "__main__":
    main()