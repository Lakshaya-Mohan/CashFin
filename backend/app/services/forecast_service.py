from datetime import date
from decimal import Decimal
import pandas as pd
from app.ml.forecaster import ForecasterService
from app.schemas.forecast import CashFlowForecast, ForecastEvent
from app.schemas.financial_state import EventType

class ForecastService:
    def __init__(self):
        self.forecaster = ForecasterService()
        
    def generate_forecast(self, df_transactions: pd.DataFrame, company_id: int, horizon_days: int = 30) -> CashFlowForecast:
        if df_transactions.empty:
            raise ValueError("No historical transactions provided for forecasting.")
            
        raw_predictions = self.forecaster.predict_next_days(df_transactions, horizon_days)
        
        events = []
        total_inflow = Decimal("0.00")
        total_outflow = Decimal("0.00")
        
        for p in raw_predictions:
            pred_amt = Decimal(str(round(p["predicted_amount"], 2)))
            hist_mae = Decimal(str(round(p["historical_mae"], 2)))
            
            # Conservative logic: if inflow, subtract MAE. If outflow, add MAE.
            if pred_amt >= 0:
                event_type = EventType.INFLOW
                conservative = max(Decimal("0.00"), pred_amt - hist_mae)
                total_inflow += pred_amt
            else:
                event_type = EventType.OUTFLOW
                conservative = pred_amt - hist_mae # more negative
                total_outflow += abs(pred_amt)
                
            events.append(
                ForecastEvent(
                    date=p["date"],
                    predicted_amount=pred_amt,
                    event_type=event_type,
                    model_name=self.forecaster.metadata.get("model_name", "Unknown"),
                    model_version=self.forecaster.metadata.get("model_version", "1.0"),
                    confidence=None,
                    historical_mae=hist_mae,
                    conservative_amount=conservative
                )
            )
            
        return CashFlowForecast(
            company_id=company_id,
            generated_at=date.today(),
            horizon_days=horizon_days,
            events=events,
            total_predicted_inflow=total_inflow,
            total_predicted_outflow=total_outflow,
            model_name=self.forecaster.metadata.get("model_name", "Unknown"),
            model_version=self.forecaster.metadata.get("model_version", "1.0")
        )
