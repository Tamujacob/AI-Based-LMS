"""
app/core/agents/local_scorer.py
─────────────────────────────────────────────────────────
Phase 4 — Local Offline Risk Scorer

Predicts loan default risk as LOW / MEDIUM / HIGH.
Works ENTIRELY OFFLINE — no internet, no API key needed.

Two modes:
  1. Rules-based fallback (always works, no training data needed)
  2. Trained ML model (better accuracy, needs 10+ completed loans)

The ML model is a scikit-learn RandomForestClassifier saved
as models/risk_model.pkl.  It is trained by model_trainer.py
and loaded automatically if the file exists.

Usage:
    score = LocalScorer.score(
        principal        = 1_000_000,
        duration_months  = 12,
        loan_type        = "Business Loan",
        occupation       = "Trader",
        monthly_income   = 800_000,
        previous_loans   = 2,
        previous_defaults= 0,
        payment_consistency = 0.90,    # 0.0–1.0
    )
    print(score.rating)        # "LOW", "MEDIUM", or "HIGH"
    print(score.confidence)    # e.g. 78 (percent)
    print(score.reasoning)     # list of explanation strings
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List


MODEL_PATH   = os.path.join("models", "risk_model.pkl")
ENCODER_PATH = os.path.join("models", "label_encoder.pkl")


@dataclass
class ScoreResult:
    """Output from the risk scorer."""
    rating:       str            # "LOW", "MEDIUM", or "HIGH"
    confidence:   int            # 0–100 percent
    prob_low:     float          = 0.0
    prob_medium:  float          = 0.0
    prob_high:    float          = 0.0
    reasoning:    List[str]      = field(default_factory=list)
    model_used:   str            = "rules"   # "rules" or "ml_model"

    def as_text(self) -> str:
        bar = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(self.rating, "⚪")
        lines = [
            f"{bar} RISK RATING:  {self.rating}  ({self.confidence}% confidence)",
            f"   Model used: {self.model_used}",
            "",
            "   Reasoning:",
        ]
        for r in self.reasoning:
            lines.append(f"   • {r}")
        return "\n".join(lines)


class LocalScorer:
    """
    Offline risk scorer. Loads ML model if available,
    falls back to rule-based scoring if not.
    """

    _model   = None
    _encoder = None
    _loaded  = False

    # ── Feature weights for rules-based scoring ───────────────────────────────
    # Each rule returns a risk_points value:
    #   0   = no risk added
    #   1   = minor risk
    #   2   = moderate risk
    #   3   = high risk
    # Total >= 5 → HIGH,  2–4 → MEDIUM,  0–1 → LOW

    @classmethod
    def score(
        cls,
        principal:            float,
        duration_months:      int,
        loan_type:            str   = "Business Loan",
        occupation:           str   = "",
        monthly_income:       float = 0,
        district:             str   = "",
        previous_loans:       int   = 0,
        previous_defaults:    int   = 0,
        payment_consistency:  float = 1.0,   # 0.0–1.0
        net_monthly_flow:     float = 0,     # from statement if available
        income_consistency:   str   = "UNKNOWN",
    ) -> ScoreResult:
        """
        Score a loan application.  Uses ML model if trained, else rules.
        """
        cls._try_load_model()

        features = {
            "principal":           principal,
            "duration_months":     duration_months,
            "loan_type":           loan_type,
            "occupation":          occupation,
            "monthly_income":      monthly_income,
            "district":            district,
            "previous_loans":      previous_loans,
            "previous_defaults":   previous_defaults,
            "payment_consistency": payment_consistency,
            "net_monthly_flow":    net_monthly_flow,
            "income_consistency":  income_consistency,
        }

        if cls._model is not None:
            return cls._ml_score(features)
        else:
            return cls._rules_score(features)

    # ── Rules-based scoring ───────────────────────────────────────────────────

    @classmethod
    def _rules_score(cls, f: dict) -> ScoreResult:
        points   = 0
        reasons  = []

        # 1. Income-to-loan ratio
        income = f["monthly_income"] or f["net_monthly_flow"]
        if income > 0:
            months = f["duration_months"] or 1
            monthly_payment = f["principal"] * 1.10 / months
            ratio = monthly_payment / income
            if ratio > 0.50:
                points += 3
                reasons.append(
                    f"Monthly payment ({ratio:.0%} of income) is very high — repayment strain likely.")
            elif ratio > 0.35:
                points += 2
                reasons.append(
                    f"Monthly payment ({ratio:.0%} of income) is above recommended 30% threshold.")
            elif ratio > 0.25:
                points += 1
                reasons.append(
                    f"Monthly payment ({ratio:.0%} of income) is within acceptable range.")
            else:
                reasons.append(
                    f"Monthly payment ({ratio:.0%} of income) is comfortably within safe limits.")
        else:
            points += 2
            reasons.append("No income data provided — cannot verify repayment capacity.")

        # 2. Previous defaults
        if f["previous_defaults"] > 1:
            points += 3
            reasons.append(f"Borrower has {f['previous_defaults']} previous defaults — very high risk.")
        elif f["previous_defaults"] == 1:
            points += 2
            reasons.append("Borrower has 1 previous default — requires careful monitoring.")
        elif f["previous_loans"] > 0:
            reasons.append(f"Borrower has {f['previous_loans']} previous loan(s) with no defaults — positive history.")

        # 3. Payment consistency (for existing borrowers)
        pc = f["payment_consistency"]
        if pc < 0.50:
            points += 2
            reasons.append(f"Payment consistency is low ({pc:.0%}) — often pays late.")
        elif pc < 0.80:
            points += 1
            reasons.append(f"Payment consistency is moderate ({pc:.0%}) — occasional late payments.")
        elif f["previous_loans"] > 0:
            reasons.append(f"Excellent payment consistency ({pc:.0%}) — consistently on time.")

        # 4. Loan duration
        if f["duration_months"] > 24:
            points += 1
            reasons.append("Long loan duration (> 24 months) increases exposure to life changes.")

        # 5. Loan type risk
        type_risk = {
            "Business Loan":          1,
            "Asset Acquisition Loan": 1,
            "School Fees Loan":       0,
            "Development Loan":       1,
            "Tax Clearance Loan":     0,
        }
        risk = type_risk.get(f["loan_type"], 1)
        if risk > 0:
            reasons.append(f"{f['loan_type']} carries slightly higher repayment variability than salary-backed loans.")

        # 6. Income consistency from statement
        if f["income_consistency"] == "LOW":
            points += 2
            reasons.append("Statement shows irregular income — cashflow gaps expected.")
        elif f["income_consistency"] == "MEDIUM":
            points += 1
            reasons.append("Statement shows moderate income consistency — some variation in cashflow.")
        elif f["income_consistency"] == "HIGH":
            reasons.append("Statement shows regular, consistent income — strong repayment foundation.")

        # 7. Occupation
        stable_occupations = ["teacher", "nurse", "doctor", "civil servant",
                               "police", "military", "government", "employed"]
        occ_lower = f["occupation"].lower()
        if any(s in occ_lower for s in stable_occupations):
            reasons.append(f"Occupation ({f['occupation']}) suggests stable salaried income.")
        elif "student" in occ_lower:
            points += 1
            reasons.append("Student borrowers typically have limited or no independent income.")

        # ── Final rating ──────────────────────────────────────────────────────
        if points >= 6:
            rating, confidence = "HIGH", min(90, 60 + points * 3)
        elif points >= 3:
            rating, confidence = "MEDIUM", min(85, 55 + points * 4)
        else:
            rating, confidence = "LOW", min(92, 75 + (3 - points) * 5)

        return ScoreResult(
            rating      = rating,
            confidence  = confidence,
            reasoning   = reasons,
            model_used  = "rules-based (no training data yet)",
        )

    # ── ML model scoring ──────────────────────────────────────────────────────

    @classmethod
    def _ml_score(cls, f: dict) -> ScoreResult:
        try:
            import numpy as np

            # Build feature vector in same order as training
            income = f["monthly_income"] or f["net_monthly_flow"] or 1
            ratio  = (f["principal"] * 1.10 / max(f["duration_months"], 1)) / income

            feature_vector = [[
                f["principal"],
                f["duration_months"],
                ratio,
                f["previous_loans"],
                f["previous_defaults"],
                f["payment_consistency"],
                f["net_monthly_flow"],
                1 if f["income_consistency"] == "HIGH" else
                0.5 if f["income_consistency"] == "MEDIUM" else 0,
            ]]

            probs   = cls._model.predict_proba(feature_vector)[0]
            classes = cls._model.classes_

            # Map classes to probs
            prob_map = {c: p for c, p in zip(classes, probs)}
            prob_low    = prob_map.get("LOW", 0)
            prob_medium = prob_map.get("MEDIUM", 0)
            prob_high   = prob_map.get("HIGH", 0)

            predicted = classes[probs.argmax()]
            confidence = int(probs.max() * 100)

            reasons = [
                f"ML model prediction based on {cls._model.n_estimators} decision trees.",
                f"Probability breakdown — LOW: {prob_low:.0%}, MEDIUM: {prob_medium:.0%}, HIGH: {prob_high:.0%}",
                f"Key factor: income-to-payment ratio is {ratio:.0%}.",
            ]
            if f["previous_defaults"] > 0:
                reasons.append(f"Previous default history weighed heavily in the prediction.")

            return ScoreResult(
                rating      = predicted,
                confidence  = confidence,
                prob_low    = prob_low,
                prob_medium = prob_medium,
                prob_high   = prob_high,
                reasoning   = reasons,
                model_used  = f"Random Forest ({cls._model.n_estimators} trees)",
            )
        except Exception as e:
            # Fallback gracefully
            result = cls._rules_score(f)
            result.reasoning.insert(0, f"ML model error ({e}) — using rules-based fallback.")
            return result

    @classmethod
    def _try_load_model(cls):
        if cls._loaded:
            return
        cls._loaded = True
        if not os.path.exists(MODEL_PATH):
            return
        try:
            import joblib
            cls._model   = joblib.load(MODEL_PATH)
            if os.path.exists(ENCODER_PATH):
                cls._encoder = joblib.load(ENCODER_PATH)
        except Exception as e:
            print(f"[LocalScorer] Could not load model: {e} — using rules-based.")
            cls._model = None

    @classmethod
    def reload_model(cls):
        """Call this after retraining to load the new model."""
        cls._loaded = False
        cls._model  = None
        cls._try_load_model()

    @classmethod
    def model_status(cls) -> str:
        cls._try_load_model()
        if cls._model:
            return f"ML model loaded ({MODEL_PATH}) — {cls._model.n_estimators} trees"
        return "Rules-based mode (no trained model found — run Model Trainer to train)"