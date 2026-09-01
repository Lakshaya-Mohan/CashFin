"""
CashFin ML Forecaster — Stage 5

PURPOSE
-------
Train a RandomForestRegressor on historical daily net cash flow and evaluate
it against a simple 7-day rolling average baseline.

IMPORTANT ARCHITECTURE NOTE
---------------------------
- This module PREDICTS uncertain future cash flows.
- It does NOT decide which obligations to pay.
- The deterministic DecisionEngine remains solely responsible for financial decisions.

CHRONOLOGICAL SPLITTING
-----------------------
Time-series data is NEVER shuffled. Split is always chronological:
  Train: first 80%
  Test:  last 20%

DATA LEAKAGE PREVENTION
-----------------------
All rolling features are computed using shift(1) in build_features(), meaning
any feature computed for date D only uses data up to D-1. The model predicts
the NEXT day's net flow, and features are derived from past data only.

CONSERVATIVE MODE
-----------------
The conservative estimated amount is:
  - For inflows:  max(0, predicted - MAE)   → assumes less income than predicted
  - For outflows: predicted + MAE            → assumes more expense than predicted
This is an approximate heuristic, NOT a statistically rigorous prediction interval.
"""

import os
import joblib
import numpy as np
import pandas as pd
from collections import deque
from datetime import datetime, timezone
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.ml.dataset import build_dataset, get_feature_columns
from app.ml.features import build_features

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

MINIMUM_HISTORY_DAYS = 30  # Configurable lower bound


class ForecasterService:
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.feature_cols = get_feature_columns()
        self.model = None
        self.metadata: dict = {}

        os.makedirs(MODELS_DIR, exist_ok=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Training & evaluation
    # ──────────────────────────────────────────────────────────────────────────

    def train_and_evaluate(
        self, df_transactions: pd.DataFrame, test_size: float = 0.20
    ) -> dict:
        """
        Build dataset, chronologically split, train RF, evaluate vs baseline.

        Returns a metadata dict with evaluation metrics, or {"error": ...} if
        there is insufficient data to produce a meaningful model.
        """
        df_dataset = build_dataset(df_transactions, min_history_days=MINIMUM_HISTORY_DAYS)

        if df_dataset is None or df_dataset.empty:
            return {"error": "Insufficient historical data. Dataset is empty."}
        if len(df_dataset) < MINIMUM_HISTORY_DAYS:
            return {
                "error": (
                    f"Insufficient historical data: {len(df_dataset)} rows "
                    f"(minimum required: {MINIMUM_HISTORY_DAYS})."
                )
            }

        # ── Chronological split ────────────────────────────────────────────
        split_idx = int(len(df_dataset) * (1.0 - test_size))
        if split_idx < 10:
            return {"error": "Training set too small after split."}

        train_df = df_dataset.iloc[:split_idx].copy()
        test_df = df_dataset.iloc[split_idx:].copy()

        X_train = train_df[self.feature_cols]
        y_train = train_df["target_net_flow"]
        X_test = test_df[self.feature_cols]
        y_test = test_df["target_net_flow"]

        # ── Baseline: 7-day historical average ────────────────────────────
        # rolling_7d_net_avg is already shifted in build_features() so it only
        # uses data strictly before the prediction date — no leakage.
        baseline_preds = test_df["rolling_7d_net_avg"].values

        baseline_mae  = float(mean_absolute_error(y_test, baseline_preds))
        baseline_rmse = float(np.sqrt(mean_squared_error(y_test, baseline_preds)))
        baseline_r2   = float(r2_score(y_test, baseline_preds))

        # ── RandomForest ──────────────────────────────────────────────────
        self.model = RandomForestRegressor(
            n_estimators=100,
            random_state=self.random_state,
            max_depth=6,
        )
        self.model.fit(X_train, y_train)
        rf_preds = self.model.predict(X_test)

        rf_mae  = float(mean_absolute_error(y_test, rf_preds))
        rf_rmse = float(np.sqrt(mean_squared_error(y_test, rf_preds)))
        rf_r2   = float(r2_score(y_test, rf_preds))

        improvement_pct = (
            (baseline_mae - rf_mae) / baseline_mae * 100.0
            if baseline_mae > 0
            else 0.0
        )

        self.metadata = {
            "model_name": "RandomForestRegressor",
            "model_version": "1.0",
            "feature_version": "1.0",
            "random_state": self.random_state,
            "training_timestamp": datetime.now(timezone.utc).isoformat(),
            "train_start_date": str(train_df["date"].min().date()),
            "train_end_date":   str(train_df["date"].max().date()),
            "test_start_date":  str(test_df["date"].min().date()),
            "test_end_date":    str(test_df["date"].max().date()),
            "n_train": int(len(train_df)),
            "n_test":  int(len(test_df)),
            # Baseline metrics
            "baseline_mae":  baseline_mae,
            "baseline_rmse": baseline_rmse,
            "baseline_r2":   baseline_r2,
            # RF metrics
            "rf_mae":  rf_mae,
            "rf_rmse": rf_rmse,
            "rf_r2":   rf_r2,
            "improvement_over_baseline_pct": improvement_pct,
        }

        self.save_model()
        return self.metadata

    # ──────────────────────────────────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────────────────────────────────

    def save_model(self) -> None:
        if self.model is not None:
            joblib.dump(self.model, os.path.join(MODELS_DIR, "rf_model.joblib"))
            joblib.dump(self.metadata, os.path.join(MODELS_DIR, "rf_metadata.joblib"))

    def load_model(self) -> bool:
        model_path = os.path.join(MODELS_DIR, "rf_model.joblib")
        meta_path  = os.path.join(MODELS_DIR, "rf_metadata.joblib")
        if os.path.exists(model_path) and os.path.exists(meta_path):
            self.model    = joblib.load(model_path)
            self.metadata = joblib.load(meta_path)
            return True
        return False

    # ──────────────────────────────────────────────────────────────────────────
    # Iterative horizon prediction
    # ──────────────────────────────────────────────────────────────────────────

    def predict_next_days(
        self, df_transactions: pd.DataFrame, horizon_days: int = 30
    ) -> list:
        """
        Iteratively predict net cash flow for the next `horizon_days` days.

        Rolling features are updated after each prediction step using the
        predicted value, so each day's prediction only uses information
        available before that day (no future leakage).

        Returns
        -------
        List of dicts: {date, predicted_amount (float), historical_mae (float)}
        """
        if self.model is None and not self.load_model():
            raise RuntimeError(
                "Model not trained. Call train_and_evaluate() first or load a saved model."
            )

        df_features = build_features(df_transactions)
        if df_features.empty:
            return []

        historical_mae = float(self.metadata.get("rf_mae", 0.0))

        # Sliding deques to track rolling windows
        last_7_net     = deque(df_features["net_cash_flow"].values[-7:],     maxlen=7)
        last_3_inflow  = deque(df_features["total_inflow"].values[-3:],      maxlen=3)
        last_3_outflow = deque(df_features["total_outflow"].values[-3:],     maxlen=3)
        last_7_inflow  = deque(df_features["total_inflow"].values[-7:],      maxlen=7)
        last_7_outflow = deque(df_features["total_outflow"].values[-7:],     maxlen=7)

        last_row  = df_features.iloc[-1].copy()
        last_date = df_features["date"].max()

        predictions: list = []

        for i in range(1, horizon_days + 1):
            pred_date = last_date + pd.Timedelta(days=i)

            feat = {
                "day_of_week":         pred_date.dayofweek,
                "day_of_month":        pred_date.day,
                "month":               pred_date.month,
                "is_weekend":          int(pred_date.dayofweek >= 5),
                "prev_net_flow":       float(last_row["net_cash_flow"]),
                "prev_transaction_count": float(last_row["transaction_count"]),
                "prev_income_count":   float(last_row["income_count"]),
                "prev_expense_count":  float(last_row["expense_count"]),
                "rolling_3d_income":   sum(last_3_inflow),
                "rolling_3d_expense":  sum(last_3_outflow),
                "rolling_7d_income":   sum(last_7_inflow),
                "rolling_7d_expense":  sum(last_7_outflow),
                "rolling_7d_net_avg":  (sum(last_7_net) / len(last_7_net)) if last_7_net else 0.0,
            }

            x_input = pd.DataFrame([feat])[self.feature_cols]
            pred_val = float(self.model.predict(x_input)[0])

            predictions.append(
                {
                    "date": pred_date.date(),
                    "predicted_amount": pred_val,
                    "historical_mae": historical_mae,
                }
            )

            # Decompose net prediction into inflow/outflow for rolling updates
            est_inflow  = pred_val if pred_val >= 0 else 0.0
            est_outflow = abs(pred_val) if pred_val < 0 else 0.0

            # Update sliding windows with predicted values
            last_7_net.append(pred_val)
            last_3_inflow.append(est_inflow)
            last_3_outflow.append(est_outflow)
            last_7_inflow.append(est_inflow)
            last_7_outflow.append(est_outflow)

            # Update last_row for next iteration's "prev_*" features
            last_row = last_row.copy()
            last_row["net_cash_flow"]      = pred_val
            last_row["total_inflow"]       = est_inflow
            last_row["total_outflow"]      = est_outflow
            last_row["transaction_count"]  = 1 if pred_val != 0 else 0
            last_row["income_count"]       = 1 if est_inflow > 0 else 0
            last_row["expense_count"]      = 1 if est_outflow > 0 else 0

        return predictions
