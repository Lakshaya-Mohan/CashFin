from datetime import date
from decimal import Decimal

from app.models.company import Company
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.counterparty import Counterparty
from app.models.payable import Payable
from app.models.receivable import Receivable
from app.db.database import SessionLocal

def seed_data():
    with SessionLocal() as session:
        # Create Company
        company = Company(name="ABC Traders", industry="Retail")
        session.add(company)
        session.commit()
        session.refresh(company)

        # Create Accounts
        account1 = Account(
            company_id=company.id,
            account_name="HDFC Current Account",
            account_type="BANK",
            current_balance=Decimal("150000.00")
        )
        account2 = Account(
            company_id=company.id,
            account_name="Petty Cash",
            account_type="CASH",
            current_balance=Decimal("5000.00")
        )
        session.add_all([account1, account2])
        session.commit()
        session.refresh(account1)
        session.refresh(account2)

        # Create Counterparties
        cp_hardware = Counterparty(
            company_id=company.id,
            name="ABC Hardware",
            counterparty_type="SUPPLIER",
            relationship_score=Decimal("0.8")
        )
        cp_customer = Counterparty(
            company_id=company.id,
            name="XYZ Customer",
            counterparty_type="CUSTOMER",
            relationship_score=Decimal("0.9")
        )
        cp_landlord = Counterparty(
            company_id=company.id,
            name="Office Landlord",
            counterparty_type="OTHER",
            relationship_score=Decimal("0.7")
        )
        session.add_all([cp_hardware, cp_customer, cp_landlord])
        session.commit()
        session.refresh(cp_hardware)
        session.refresh(cp_customer)
        session.refresh(cp_landlord)

        # Create Transactions
        t1 = Transaction(
            account_id=account1.id,
            transaction_date=date(2026, 8, 1),
            amount=Decimal("100000.00"),
            transaction_type="INCOME",
            category="Sales",
            description="Monthly sales deposit"
        )
        t2 = Transaction(
            account_id=account1.id,
            transaction_date=date(2026, 8, 5),
            amount=Decimal("20000.00"),
            transaction_type="EXPENSE",
            category="Rent",
            description="Office rent payment"
        )
        session.add_all([t1, t2])

        # Create Payables
        p1 = Payable(
            company_id=company.id,
            counterparty_id=cp_hardware.id,
            amount=Decimal("30000.00"),
            due_date=date(2026, 9, 15),
            status="PENDING",
            description="Hardware supplies"
        )
        p2 = Payable(
            company_id=company.id,
            counterparty_id=cp_landlord.id,
            amount=Decimal("40000.00"),
            due_date=date(2026, 9, 1),
            status="PENDING",
            description="Office Rent"
        )
        # Employee salary usually has its own CP or is just a general payable
        cp_employee = Counterparty(
            company_id=company.id,
            name="Employee",
            counterparty_type="OTHER"
        )
        session.add(cp_employee)
        session.commit()
        session.refresh(cp_employee)
        
        p3 = Payable(
            company_id=company.id,
            counterparty_id=cp_employee.id,
            amount=Decimal("50000.00"),
            due_date=date(2026, 8, 31),
            status="PENDING",
            description="Employee Salary"
        )
        session.add_all([p1, p2, p3])

        # Create Receivables
        r1 = Receivable(
            company_id=company.id,
            counterparty_id=cp_customer.id,
            amount=Decimal("60000.00"),
            expected_date=date(2026, 9, 10),
            status="EXPECTED",
            description="Invoice #1234"
        )
        r2 = Receivable(
            company_id=company.id,
            counterparty_id=cp_customer.id,  # Reusing for "Another customer" conceptually or create new
            amount=Decimal("20000.00"),
            expected_date=date(2026, 9, 20),
            status="EXPECTED",
            description="Invoice #1235"
        )
        session.add_all([r1, r2])

        session.commit()
        print("Database seeded successfully.")

if __name__ == "__main__":
    seed_data()
