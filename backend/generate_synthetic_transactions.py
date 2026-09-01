import csv
import random
from datetime import date, timedelta
from decimal import Decimal

def generate_synthetic_transactions(filepath="data/samples/historical_transactions.csv", num_days=180, company_id=1, account_id=1):
    start_date = date(2026, 8, 1) - timedelta(days=num_days)
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["company_id", "account_id", "transaction_date", "amount", "transaction_type", "category", "description"])
        
        for i in range(num_days):
            current_date = start_date + timedelta(days=i)
            
            # Weekend check
            is_weekend = current_date.weekday() >= 5
            
            # Daily chance of recurring transactions
            if current_date.day == 1:
                # Rent (outflow)
                writer.writerow([company_id, account_id, current_date, "-50000.00", "EXPENSE", "Rent", "Office Rent"])
                
            if current_date.day == 28:
                # Salaries (outflow)
                writer.writerow([company_id, account_id, current_date, "-150000.00", "EXPENSE", "Payroll", "Employee Salaries"])
                
            # Random daily inflows (customers paying)
            if not is_weekend:
                if random.random() < 0.7:  # 70% chance of getting paid
                    amount = round(random.uniform(5000, 35000), 2)
                    writer.writerow([company_id, account_id, current_date, f"{amount:.2f}", "INCOME", "Sales", "Customer Payment"])
                    
            # Occasional irregular expenses
            if random.random() < 0.2:
                amount = round(random.uniform(1000, 10000), 2)
                writer.writerow([company_id, account_id, current_date, f"-{amount:.2f}", "EXPENSE", "Operations", "Office Supplies"])
                
            # Supplier payments (e.g. every 14 days)
            if i % 14 == 0:
                amount = round(random.uniform(20000, 80000), 2)
                writer.writerow([company_id, account_id, current_date, f"-{amount:.2f}", "EXPENSE", "Inventory", "Supplier Invoice"])

if __name__ == "__main__":
    generate_synthetic_transactions()
    print("Synthetic transactions generated at data/samples/historical_transactions.csv")
