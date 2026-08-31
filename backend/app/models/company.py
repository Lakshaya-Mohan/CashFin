from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.counterparty import Counterparty
    from app.models.payable import Payable
    from app.models.receivable import Receivable


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    industry: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="company", cascade="all, delete-orphan")
    counterparties: Mapped[list["Counterparty"]] = relationship("Counterparty", back_populates="company", cascade="all, delete-orphan")
    payables: Mapped[list["Payable"]] = relationship("Payable", back_populates="company", cascade="all, delete-orphan")
    receivables: Mapped[list["Receivable"]] = relationship("Receivable", back_populates="company", cascade="all, delete-orphan")