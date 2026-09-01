import pandas as pd

def build_features(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Builds time-aware rolling features for forecasting next-day net cash flow.
    Expects df_transactions to have: ['transaction_date', 'amount', 'transaction_type']
    """
    if df_transactions.empty:
        return pd.DataFrame()
        
    # Ensure correct types
    df = df_transactions.copy()
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    df['amount'] = df['amount'].astype(float)
    
    # Aggregate to daily
    # Inflows are positive, outflows are negative. Wait, transaction type might dictate sign.
    # Let's standardize: INCOME -> positive, EXPENSE -> positive for aggregation, then subtract.
    
    df['inflow'] = df.apply(lambda row: row['amount'] if row['transaction_type'] == 'INCOME' else 0.0, axis=1)
    df['outflow'] = df.apply(lambda row: abs(row['amount']) if row['transaction_type'] == 'EXPENSE' else 0.0, axis=1)
    df['net_flow'] = df['inflow'] - df['outflow']
    
    # We want a full date range so rolling features don't skip days with 0 transactions
    min_date = df['transaction_date'].min()
    max_date = df['transaction_date'].max()
    full_dates = pd.date_range(start=min_date, end=max_date, freq='D')
    
    daily = df.groupby('transaction_date').agg(
        total_inflow=('inflow', 'sum'),
        total_outflow=('outflow', 'sum'),
        net_cash_flow=('net_flow', 'sum'),
        transaction_count=('amount', 'count'),
        income_count=('inflow', lambda x: (x > 0).sum()),
        expense_count=('outflow', lambda x: (x > 0).sum())
    ).reindex(full_dates, fill_value=0.0).reset_index(names='date')
    
    # Calendar features
    daily['day_of_week'] = daily['date'].dt.dayofweek
    daily['day_of_month'] = daily['date'].dt.day
    daily['month'] = daily['date'].dt.month
    daily['is_weekend'] = daily['day_of_week'].isin([5, 6]).astype(int)
    
    # Time-aware historical rolling features
    # Shift by 1 to ensure we only use data strictly BEFORE the current date (no leakage)
    
    shifted = daily.shift(1)
    
    daily['prev_net_flow'] = shifted['net_cash_flow'].fillna(0)
    daily['prev_transaction_count'] = shifted['transaction_count'].fillna(0)
    daily['prev_income_count'] = shifted['income_count'].fillna(0)
    daily['prev_expense_count'] = shifted['expense_count'].fillna(0)
    
    daily['rolling_3d_income'] = shifted['total_inflow'].rolling(window=3, min_periods=1).sum().fillna(0)
    daily['rolling_3d_expense'] = shifted['total_outflow'].rolling(window=3, min_periods=1).sum().fillna(0)
    daily['rolling_7d_income'] = shifted['total_inflow'].rolling(window=7, min_periods=1).sum().fillna(0)
    daily['rolling_7d_expense'] = shifted['total_outflow'].rolling(window=7, min_periods=1).sum().fillna(0)
    daily['rolling_7d_net_avg'] = shifted['net_cash_flow'].rolling(window=7, min_periods=1).mean().fillna(0)
    
    return daily
