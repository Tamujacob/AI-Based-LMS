"""
app/core/agents/model_trainer.py
─────────────────────────────────────────────────────────
Phase 6 — Model Trainer

Trains the local risk scoring model from completed and
defaulted loans in the database.

The model learns from real Bingongold Credit repayment
history — it only knows about YOUR loans, nothing else.

Minimum data needed: 10 completed or defaulted loans.
Best accuracy: 50+ completed loans.

The trained model is saved as models/risk_model.pkl.
LocalScorer automatically uses it after training.

Usage (from Agent screen):
    result = ModelTrainer.train()
    print(result["message"])
    print(result["accuracy"])
"""

import os


MODEL_DIR    = "models"
MODEL_PATH   = os.path.join(MODEL_DIR, "risk_model.pkl")
ENCODER_PATH = os.path.join(MODEL_DIR, "label_encoder.pkl")


class ModelTrainer:

    @staticmethod
    def get_training_stats() -> dict:
        """
        Return how many training samples are available without training.
        Call this before training to check readiness.
        """
        try:
            from app.database.connection import get_db
            from app.core.models.loan import Loan, LoanStatus
            from app.core.models.repayment import Repayment

            with get_db() as db:
                completed = db.query(Loan).filter(
                    Loan.status == LoanStatus.completed).count()
                defaulted = db.query(Loan).filter(
                    Loan.status == LoanStatus.defaulted).count()
                total_loans = db.query(Loan).count()

            return {
                "completed":    completed,
                "defaulted":    defaulted,
                "total_samples": completed + defaulted,
                "total_loans":  total_loans,
                "model_exists": os.path.exists(MODEL_PATH),
                "ready":        (completed + defaulted) >= 10,
            }
        except Exception as e:
            return {"error": str(e), "ready": False}

    @staticmethod
    def train(progress_callback=None) -> dict:
        """
        Train the risk model from loan history.

        Args:
            progress_callback: Optional function(message: str) called with status updates.

        Returns:
            dict with keys: success, message, accuracy, samples_used
        """
        def _log(msg):
            print(f"[ModelTrainer] {msg}")
            if progress_callback:
                progress_callback(msg)

        # ── Check dependencies ────────────────────────────────────────────────
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import cross_val_score
            from sklearn.preprocessing import LabelEncoder
            import numpy as np
            import joblib
        except ImportError as e:
            return {
                "success": False,
                "message": f"Missing library: {e}\nRun: pip install scikit-learn joblib",
                "accuracy": 0, "samples_used": 0,
            }

        _log("Collecting training data from database...")

        # ── Collect training data ─────────────────────────────────────────────
        try:
            from app.database.connection import get_db
            from app.core.models.loan import Loan, LoanStatus
            from app.core.models.client import Client
            from app.core.models.repayment import Repayment
            from sqlalchemy import func

            features_list = []
            labels_list   = []

            with get_db() as db:
                # Get completed loans (LOW risk outcome)
                completed_loans = db.query(Loan).filter(
                    Loan.status == LoanStatus.completed).all()

                # Get defaulted loans (HIGH risk outcome)
                defaulted_loans = db.query(Loan).filter(
                    Loan.status == LoanStatus.defaulted).all()

                all_training_loans = [
                    (loan, "LOW") for loan in completed_loans
                ] + [
                    (loan, "HIGH") for loan in defaulted_loans
                ]

                if len(all_training_loans) < 10:
                    return {
                        "success": False,
                        "message": (
                            f"Not enough training data. "
                            f"Found {len(all_training_loans)} completed/defaulted loans. "
                            f"Need at least 10. Keep using the system and retrain later."
                        ),
                        "accuracy": 0,
                        "samples_used": len(all_training_loans),
                    }

                _log(f"Found {len(all_training_loans)} training samples. Building features...")

                for loan, label in all_training_loans:
                    client = db.query(Client).filter_by(id=loan.client_id).first()

                    # Count previous loans by this client (before this one)
                    prev_loans = db.query(Loan).filter(
                        Loan.client_id == loan.client_id,
                        Loan.id < loan.id
                    ).count()

                    prev_defaults = db.query(Loan).filter(
                        Loan.client_id == loan.client_id,
                        Loan.id < loan.id,
                        Loan.status == LoanStatus.defaulted
                    ).count()

                    # Payment consistency: ratio of on-time payments
                    repayments = db.query(Repayment).filter_by(loan_id=loan.id).all()
                    if repayments and loan.monthly_installment:
                        on_time = sum(
                            1 for r in repayments
                            if r.payment_date and loan.due_date
                            and r.payment_date <= loan.due_date
                        )
                        consistency = on_time / max(len(repayments), 1)
                    else:
                        consistency = 0.5

                    # Income estimate
                    income = 0
                    if client and client.monthly_income:
                        try:
                            income = float(str(client.monthly_income).replace(",", ""))
                        except Exception:
                            income = 0

                    principal = float(loan.principal_amount or 0)
                    months    = int(loan.duration_months or 12)
                    income_safe = income if income > 0 else 1
                    ratio = (principal * 1.10 / months) / income_safe

                    features_list.append([
                        principal,
                        months,
                        ratio,
                        prev_loans,
                        prev_defaults,
                        consistency,
                        0,    # net_monthly_flow (unknown for historical loans)
                        0.5,  # income_consistency (unknown for historical)
                    ])
                    labels_list.append(label)

        except Exception as e:
            return {"success": False, "message": f"Database error: {e}",
                    "accuracy": 0, "samples_used": 0}

        _log("Training Random Forest model...")

        # ── Train ─────────────────────────────────────────────────────────────
        try:
            import numpy as np
            X = np.array(features_list)
            y = np.array(labels_list)

            model = RandomForestClassifier(
                n_estimators     = 100,
                max_depth        = 8,
                min_samples_leaf = 2,
                random_state     = 42,
                class_weight     = "balanced",
            )

            # Cross-validate if enough data
            if len(X) >= 20:
                cv_scores = cross_val_score(model, X, y, cv=min(5, len(X)//4), scoring="accuracy")
                accuracy  = round(cv_scores.mean() * 100, 1)
                _log(f"Cross-validation accuracy: {accuracy}%")
            else:
                accuracy = 0

            model.fit(X, y)

            # ── Save ──────────────────────────────────────────────────────────
            os.makedirs(MODEL_DIR, exist_ok=True)
            joblib.dump(model, MODEL_PATH)
            _log(f"Model saved to {MODEL_PATH}")

            # Reload in LocalScorer
            from app.core.agents.local_scorer import LocalScorer
            LocalScorer.reload_model()

            return {
                "success":      True,
                "message": (
                    f"Model trained successfully from {len(X)} loan records.\n"
                    f"Accuracy: {accuracy}%\n"
                    f"Model saved to: {MODEL_PATH}\n"
                    f"The risk scorer will now use this model automatically."
                ),
                "accuracy":     accuracy,
                "samples_used": len(X),
            }

        except Exception as e:
            return {"success": False, "message": f"Training error: {e}",
                    "accuracy": 0, "samples_used": 0}