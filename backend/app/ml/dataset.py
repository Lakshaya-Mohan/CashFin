import pandas as pd
from typing import Tuple, List
from app.ml.features import build_features

def build_dataset(df_transactions: pd.DataFrame, min_history_days: int = 30) -> pd.DataFrame:
    """
    Builds the forecasting dataset.
    Target: next day's net cash flow.
    """
    if df_transactions.empty:
        return pd.DataFrame()
        
    df_features = build_features(df_transactions)
    if df_features.empty or len(df_features) < min_history_days:
        return pd.DataFrame()
        
    # The target is the NEXT day's net cash flow
    # We shift net_cash_flow backwards by 1
    # Example: If today is Day 5, target_net_flow is the net_cash_flow of Day 6
    df_features['target_net_flow'] = df_features['net_cash_flow'].shift(-1)
    
    # Drop the last row because it won't have a target
    df_dataset = df_features.dropna(subset=['target_net_flow']).copy()
    
    # Ensure we only return if we have enough history
    # The first few rows of df_features will have 0s for rolling, but it's acceptable for MVP
    
    return df_dataset

def get_feature_columns() -> List[str]:
    return [
        'day_of_week', 'day_of_month', 'month', 'is_weekend',
        'prev_net_flow', 'prev_transaction_count', 'prev_income_count', 'prev_expense_count',
        'rolling_3d_income', 'rolling_3d_expense', 
        'rolling_7d_income', 'rolling_7d_expense', 'rolling_7d_net_avg'
    ]
