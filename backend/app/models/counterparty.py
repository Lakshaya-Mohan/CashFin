from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, DateTime, Numeric, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.payable import Payable
    from app.models.receivable import Receivable


class Counterparty(Base):
    __tablename__ = "counterparties"
    __table_args__ = (
        CheckConstraint('relationship_score >= 0 AND relationship_score <= 1', name='chk_counterparty_relationship_score'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    counterparty_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CUSTOMER, SUPPLIER, OTHER
    
    relationship_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal('0.5000'))
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="counterparties")
    payables: Mapped[list["Payable"]] = relationship("Payable", back_populates="counterparty", cascade="all, delete-orphan")
    receivables: Mapped[list["Receivable"]] = relationship("Receivable", back_populates="counterparty", cascade="all, delete-orphan")
