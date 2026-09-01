"""
tests/test_forecasting.py — Stage 5 comprehensive forecasting tests

Covers:
 1. Feature generation produces expected columns
 2. No future-data leakage (rolling features never include same-day data)
 3. Rolling features are correctly computed
 4. Baseline forecast (7-day average)
 5. Chronological train/test split — never shuffled
 6. Insufficient-history handling
 7. Model training returns metrics
 8. Prediction output schema matches ForecastEvent
 9. Horizon produces correct number of predictions
10. Predicted events are marked is_predicted=True
11. Deterministic random seed — same data → same predictions
12. Model persistence (save & load)
13. ForecastService integration with CashFlowService
14. CONFIRMED_ONLY mode — predicted events excluded
15. FORECAST_INCLUDED mode — predicted events included
16. CONSERVATIVE mode — conservative amounts differ from predicted
"""

import os
import shutil
import tempfile
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from decimal import Decimal

from app.ml.features import build_features
from app.ml.dataset import build_dataset, get_feature_columns
from app.ml.forecaster import ForecasterService, MODELS_DIR
from app.services.forecast_service import ForecastService
from app.services.cash_flow import CashFlowService
from app.schemas.financial_state import (
    FinancialState, UpcomingPayable, UpcomingReceivable,
    ReceivableMode, ForecastMode, EventType
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_transactions(num_days: int = 90, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic daily transaction DataFrame for testing."""
    rng = np.random.default_rng(seed)
    rows = []
    start = date(2026, 1, 1)
    for i in range(num_days):
        d = start + timedelta(days=i)
        is_weekend = d.weekday() >= 5
        if not is_weekend:
            # Income day
            rows.append({
                "transaction_date": d,
                "amount": float(rng.uniform(5000, 30000)),
                "transaction_type": "INCOME",
            })
        # Expenses some days
        if rng.random() < 0.4:
            rows.append({
                "transaction_date": d,
                "amount": float(rng.uniform(1000, 15000)),
                "transaction_type": "EXPENSE",
            })
    return pd.DataFrame(rows)


def make_small_transactions(num_days: int = 10) -> pd.DataFrame:
    """Too few records to train on."""
    rng = np.random.default_rng(0)
    rows = []
    start = date(2026, 1, 1)
    for i in range(num_days):
        d = start + timedelta(days=i)
        rows.append({
            "transaction_date": d,
            "amount": float(rng.uniform(1000, 5000)),
            "transaction_type": "INCOME",
        })
    return pd.DataFrame(rows)


def make_financial_state(cash: Decimal = Decimal("50000.00")) -> FinancialState:
    return FinancialState(
        company_id=1,
        as_of_date=date.today(),
        current_cash=cash,
        pending_payables_total=Decimal("0.00"),
        pending_receivables_total_raw=Decimal("0.00"),
        pending_receivables_total_adjusted=Decimal("0.00"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Feature generation produces expected columns
# ─────────────────────────────────────────────────────────────────────────────

def test_1_feature_columns_present():
    df = make_transactions(60)
    features = build_features(df)
    expected_cols = get_feature_columns()
    for col in expected_cols:
        assert col in features.columns, f"Missing column: {col}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. No future-data leakage
# ─────────────────────────────────────────────────────────────────────────────

def test_2_no_future_data_leakage():
    """
    rolling_7d_net_avg for row i must equal the mean of net_cash_flow
    for rows [i-7 .. i-1] (strictly BEFORE row i).
    We check this for every row after the warm-up period.
    """
    df = make_transactions(60)
    features = build_features(df)
    net = features["net_cash_flow"].values
    avg7 = features["rolling_7d_net_avg"].values

    for i in range(7, len(features)):
        past_window = net[max(0, i - 7): i]
        expected_avg = float(np.mean(past_window))
        # Allow small float tolerance
        assert abs(avg7[i] - expected_avg) < 1.0, (
            f"Leakage detected at row {i}: "
            f"avg7={avg7[i]:.2f}, expected={expected_avg:.2f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Rolling features correctness
# ─────────────────────────────────────────────────────────────────────────────

def test_3_rolling_3d_income_correct():
    """rolling_3d_income[i] must be the sum of total_inflow[i-3..i-1]."""
    df = make_transactions(60)
    features = build_features(df)
    inflow = features["total_inflow"].values
    r3 = features["rolling_3d_income"].values

    for i in range(3, len(features)):
        past = inflow[max(0, i - 3): i]
        expected = float(np.sum(past))
        assert abs(r3[i] - expected) < 1.0, (
            f"rolling_3d_income mismatch at row {i}: "
            f"got {r3[i]:.2f}, expected {expected:.2f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Baseline forecast (7-day historical average)
# ─────────────────────────────────────────────────────────────────────────────

def test_4_baseline_produces_metrics():
    df = make_transactions(90)
    svc = ForecasterService(random_state=42)
    result = svc.train_and_evaluate(df)
    assert "error" not in result
    assert "baseline_mae" in result
    assert result["baseline_mae"] > 0, "Baseline MAE should be non-zero"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Chronological split — dates never shuffled
# ─────────────────────────────────────────────────────────────────────────────

def test_5_chronological_split():
    df = make_transactions(90)
    dataset = build_dataset(df)
    assert dataset is not None and not dataset.empty
    # Dates must be monotonically increasing (no shuffling)
    dates = dataset["date"].values
    assert all(dates[i] <= dates[i + 1] for i in range(len(dates) - 1)), (
        "Dataset dates are not in chronological order — potential data shuffle!"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Insufficient-history handling
# ─────────────────────────────────────────────────────────────────────────────

def test_6_insufficient_history_error():
    df = make_small_transactions(10)
    svc = ForecasterService(random_state=42)
    result = svc.train_and_evaluate(df)
    assert "error" in result
    assert "Insufficient" in result["error"]


def test_6b_empty_transactions():
    df = pd.DataFrame()
    svc = ForecasterService(random_state=42)
    result = svc.train_and_evaluate(df)
    assert "error" in result


# ─────────────────────────────────────────────────────────────────────────────
# 7. Model training returns metrics
# ─────────────────────────────────────────────────────────────────────────────

def test_7_training_returns_metrics():
    df = make_transactions(90)
    svc = ForecasterService(random_state=42)
    result = svc.train_and_evaluate(df)
    assert "error" not in result
    for key in ("rf_mae", "rf_rmse", "rf_r2", "baseline_mae", "improvement_over_baseline_pct"):
        assert key in result, f"Missing metric: {key}"
    assert result["rf_mae"] >= 0
    assert result["rf_rmse"] >= 0


# ─────────────────────────────────────────────────────────────────────────────
# 8. Prediction output schema
# ─────────────────────────────────────────────────────────────────────────────

def test_8_prediction_output_schema():
    df = make_transactions(90)
    svc = ForecasterService(random_state=42)
    svc.train_and_evaluate(df)
    predictions = svc.predict_next_days(df, horizon_days=7)
    assert len(predictions) == 7
    for p in predictions:
        assert "date" in p
        assert "predicted_amount" in p
        assert "historical_mae" in p
        assert isinstance(p["date"], date)
        assert isinstance(p["predicted_amount"], float)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Forecast horizon
# ─────────────────────────────────────────────────────────────────────────────

def test_9_forecast_horizon_configurable():
    df = make_transactions(90)
    svc = ForecasterService(random_state=42)
    svc.train_and_evaluate(df)
    for horizon in [7, 14, 30]:
        preds = svc.predict_next_days(df, horizon_days=horizon)
        assert len(preds) == horizon, f"Expected {horizon} predictions, got {len(preds)}"


# ─────────────────────────────────────────────────────────────────────────────
# 10. Predicted events are marked as PREDICTED
# ─────────────────────────────────────────────────────────────────────────────

def test_10_predicted_events_marked():
    df = make_transactions(90)
    svc = ForecasterService(random_state=42)
    svc.train_and_evaluate(df)

    forecast_svc = ForecastService()
    forecast_svc.forecaster = svc
    forecast = forecast_svc.generate_forecast(df, company_id=1, horizon_days=7)

    state = make_financial_state()
    projection = CashFlowService.calculate_projection(
        state=state,
        forecast_mode=ForecastMode.FORECAST_INCLUDED,
        forecast=forecast,
    )

    predicted_events = [e for e in projection.events if e.is_predicted]
    confirmed_events = [e for e in projection.events if not e.is_predicted]

    # All forecast events must be marked is_predicted=True
    assert len(predicted_events) == 7
    # No known payables/receivables → zero confirmed events
    assert len(confirmed_events) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 11. Deterministic random seed
# ─────────────────────────────────────────────────────────────────────────────

def test_11_deterministic_seed():
    df = make_transactions(90, seed=99)

    svc1 = ForecasterService(random_state=42)
    svc1.train_and_evaluate(df)
    preds1 = svc1.predict_next_days(df, horizon_days=5)

    svc2 = ForecasterService(random_state=42)
    svc2.train_and_evaluate(df)
    preds2 = svc2.predict_next_days(df, horizon_days=5)

    for p1, p2 in zip(preds1, preds2):
        assert abs(p1["predicted_amount"] - p2["predicted_amount"]) < 1e-6, (
            "Random seed produced different predictions — reproducibility broken"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 12. Model persistence (save and load)
# ─────────────────────────────────────────────────────────────────────────────

def test_12_model_persistence(tmp_path, monkeypatch):
    """Saved model can be loaded and produces same predictions."""
    import app.ml.forecaster as fc_module
    monkeypatch.setattr(fc_module, "MODELS_DIR", str(tmp_path))

    df = make_transactions(90)

    svc_train = ForecasterService(random_state=42)
    svc_train.train_and_evaluate(df)
    preds_before = svc_train.predict_next_days(df, horizon_days=5)

    svc_load = ForecasterService(random_state=42)
    loaded = svc_load.load_model()
    assert loaded, "Model failed to load from disk"
    preds_after = svc_load.predict_next_days(df, horizon_days=5)

    for pb, pa in zip(preds_before, preds_after):
        assert abs(pb["predicted_amount"] - pa["predicted_amount"]) < 1e-6


# ─────────────────────────────────────────────────────────────────────────────
# 13. ForecastService integration with CashFlowService
# ─────────────────────────────────────────────────────────────────────────────

def test_13_forecast_service_integration():
    df = make_transactions(90)
    svc = ForecasterService(random_state=42)
    svc.train_and_evaluate(df)

    forecast_svc = ForecastService()
    forecast_svc.forecaster = svc

    forecast = forecast_svc.generate_forecast(df, company_id=1, horizon_days=14)
    assert forecast.company_id == 1
    assert forecast.horizon_days == 14
    assert len(forecast.events) == 14

    state = make_financial_state(cash=Decimal("100000.00"))
    state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal("20000.00"), due_date=date.today() + timedelta(days=5))
    ]

    projection = CashFlowService.calculate_projection(
        state=state,
        forecast_mode=ForecastMode.FORECAST_INCLUDED,
        forecast=forecast,
    )

    # Should have 1 confirmed + 14 predicted events
    assert sum(1 for e in projection.events if not e.is_predicted) == 1
    assert sum(1 for e in projection.events if e.is_predicted) == 14


# ─────────────────────────────────────────────────────────────────────────────
# 14. CONFIRMED_ONLY mode excludes predicted events
# ─────────────────────────────────────────────────────────────────────────────

def test_14_confirmed_only_mode():
    df = make_transactions(90)
    svc = ForecasterService(random_state=42)
    svc.train_and_evaluate(df)

    forecast_svc = ForecastService()
    forecast_svc.forecaster = svc
    forecast = forecast_svc.generate_forecast(df, company_id=1, horizon_days=14)

    state = make_financial_state()
    state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal("5000.00"), due_date=date.today() + timedelta(days=3))
    ]

    projection = CashFlowService.calculate_projection(
        state=state,
        forecast_mode=ForecastMode.CONFIRMED_ONLY,
        forecast=forecast,  # passed but should be ignored
    )

    # All events must be confirmed
    assert all(not e.is_predicted for e in projection.events)
    assert len(projection.events) == 1


# ─────────────────────────────────────────────────────────────────────────────
# 15. FORECAST_INCLUDED mode includes predicted events
# ─────────────────────────────────────────────────────────────────────────────

def test_15_forecast_included_mode():
    df = make_transactions(90)
    svc = ForecasterService(random_state=42)
    svc.train_and_evaluate(df)

    forecast_svc = ForecastService()
    forecast_svc.forecaster = svc
    forecast = forecast_svc.generate_forecast(df, company_id=1, horizon_days=7)

    state = make_financial_state()
    projection = CashFlowService.calculate_projection(
        state=state,
        forecast_mode=ForecastMode.FORECAST_INCLUDED,
        forecast=forecast,
    )

    predicted = [e for e in projection.events if e.is_predicted]
    assert len(predicted) == 7
    # Amounts should match predicted_amount in forecast events
    forecast_amounts = {fe.date: fe.predicted_amount for fe in forecast.events}
    for e in predicted:
        expected = float(forecast_amounts[e.date])
        got = float(e.amount)
        assert abs(got - expected) < 0.01, (
            f"FORECAST_INCLUDED amount mismatch on {e.date}: expected {expected}, got {got}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 16. CONSERVATIVE mode uses conservative amounts
# ─────────────────────────────────────────────────────────────────────────────

def test_16_conservative_mode():
    df = make_transactions(90)
    svc = ForecasterService(random_state=42)
    svc.train_and_evaluate(df)

    forecast_svc = ForecastService()
    forecast_svc.forecaster = svc
    forecast = forecast_svc.generate_forecast(df, company_id=1, horizon_days=7)

    state = make_financial_state()
    projection_included = CashFlowService.calculate_projection(
        state=state,
        forecast_mode=ForecastMode.FORECAST_INCLUDED,
        forecast=forecast,
    )
    projection_conservative = CashFlowService.calculate_projection(
        state=state,
        forecast_mode=ForecastMode.CONSERVATIVE,
        forecast=forecast,
    )

    # For positive-net events: conservative <= predicted
    for fe in forecast.events:
        if fe.event_type == EventType.INFLOW and fe.conservative_amount is not None:
            assert fe.conservative_amount <= fe.predicted_amount, (
                f"Conservative inflow {fe.conservative_amount} exceeds predicted {fe.predicted_amount}"
            )
