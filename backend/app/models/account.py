from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.transaction import Transaction


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., BANK, CASH
    
    current_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal('0.00'))
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
