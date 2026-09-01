from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.financial_state import EventType

class ForecastEvent(BaseModel):
    date: date
    predicted_amount: Decimal
    event_type: EventType
    model_name: str
    model_version: str
    confidence: Optional[Decimal] = None
    historical_mae: Optional[Decimal] = None
    conservative_amount: Optional[Decimal] = None
    
    model_config = ConfigDict(from_attributes=True)

class CashFlowForecast(BaseModel):
    company_id: int
    generated_at: date
    horizon_days: int
    events: List[ForecastEvent]
    total_predicted_inflow: Decimal
    total_predicted_outflow: Decimal
    model_name: str
    model_version: str
    
    model_config = ConfigDict(from_attributes=True)
