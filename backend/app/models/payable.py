from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Date, DateTime, Numeric, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.counterparty import Counterparty


class Payable(Base):
    __tablename__ = "payables"
    __table_args__ = (
        CheckConstraint('urgency >= 1 AND urgency <= 5', name='chk_payable_urgency'),
        CheckConstraint('penalty_risk >= 1 AND penalty_risk <= 5', name='chk_payable_penalty_risk'),
        CheckConstraint('flexibility >= 1 AND flexibility <= 5', name='chk_payable_flexibility'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    counterparty_id: Mapped[int] = mapped_column(ForeignKey("counterparties.id"), nullable=False)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    urgency: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    penalty_risk: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    flexibility: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # External reference (e.g., purchase order, expense ID). Used for idempotent ingestion.
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="payables")
    counterparty: Mapped["Counterparty"] = relationship("Counterparty", back_populates="payables")
