from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.company import Company
from app.schemas.company import CompanySchema

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get(
    "",
    response_model=List[CompanySchema],
    summary="List all companies",
    description="Retrieves a list of all registered companies.",
)
def list_companies(db: Session = Depends(get_db)):
    companies = db.execute(select(Company)).scalars().all()
    return companies


@router.get(
    "/{company_id}",
    response_model=CompanySchema,
    summary="Get company details",
    description="Retrieves details for a specific company by ID.",
)
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.execute(select(Company).where(Company.id == company_id)).scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    return company
