from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Date, DateTime, Numeric, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.counterparty import Counterparty


class Receivable(Base):
    __tablename__ = "receivables"
    __table_args__ = (
        CheckConstraint('confidence >= 0 AND confidence <= 1', name='chk_receivable_confidence'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    counterparty_id: Mapped[int] = mapped_column(ForeignKey("counterparties.id"), nullable=False)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    expected_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal('0.8000'))
    
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Invoice number or other external reference. Used for idempotent ingestion.
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="receivables")
    counterparty: Mapped["Counterparty"] = relationship("Counterparty", back_populates="receivables")
