import json
import os
import tempfile
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status, Body, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.account import Account
from app.models.company import Company
from app.schemas.ingestion import IngestionResult
from app.services.ingestion_service import (
    ingest_bank_csv,
    ingest_expenses_json,
    ingest_invoices_json,
    ingest_receipt_image,
)

router = APIRouter(prefix="/companies", tags=["Ingestion"])


def _validate_company_and_account(company_id: int, account_id: Optional[int], db: Session) -> Account:
    company = db.execute(select(Company).where(Company.id == company_id)).scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    if account_id is not None:
        account = db.execute(select(Account).where(Account.id == account_id)).scalar_one_or_none()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        if account.company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account does not belong to the specified company."
            )
        return account
    return None


@router.post(
    "/{company_id}/accounts/{account_id}/transactions/import",
    response_model=IngestionResult,
    summary="Import bank statement CSV",
    description="Ingests bank statement CSV file for a specific account.",
)
async def import_bank_csv(
    company_id: int,
    account_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _validate_company_and_account(company_id, account_id, db)

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only CSV files are allowed."
        )

    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = ingest_bank_csv(
            file_path=tmp_path,
            company_id=company_id,
            account_id=account_id,
            session=db,
        )
        return result
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post(
    "/{company_id}/invoices/import",
    response_model=IngestionResult,
    summary="Import customer invoices JSON",
    description="Ingests customer invoices from a JSON file upload or JSON payload.",
)
async def import_invoices_json_endpoint(
    company_id: int,
    request: Request,
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    company = db.execute(select(Company).where(Company.id == company_id)).scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    json_str = None

    # Check for uploaded file first
    if file is not None and file.filename:
        content = await file.read()
        json_str = content.decode("utf-8")
    else:
        # Fallback to reading request JSON body
        try:
            body_data = await request.json()
            if body_data is not None:
                json_str = json.dumps(body_data)
        except Exception:
            pass

    if not json_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a JSON file upload or JSON body payload must be provided."
        )

    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json", encoding="utf-8") as tmp:
        tmp.write(json_str)
        tmp_path = tmp.name

    try:
        result = ingest_invoices_json(
            file_path=tmp_path,
            company_id=company_id,
            session=db,
        )
        return result
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post(
    "/{company_id}/expenses/import",
    response_model=IngestionResult,
    summary="Import vendor expenses JSON",
    description="Ingests vendor expenses from a JSON file upload or JSON payload.",
)
async def import_expenses_json_endpoint(
    company_id: int,
    request: Request,
    account_id: Optional[int] = Query(default=None, description="Account ID for paid expenses"),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    if account_id is not None:
        _validate_company_and_account(company_id, account_id, db)
    else:
        company = db.execute(select(Company).where(Company.id == company_id)).scalar_one_or_none()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found"
            )

    json_str = None

    # Check for uploaded file first
    if file is not None and file.filename:
        content = await file.read()
        json_str = content.decode("utf-8")
    else:
        # Fallback to reading request JSON body
        try:
            body_data = await request.json()
            if body_data is not None:
                json_str = json.dumps(body_data)
        except Exception:
            pass

    if not json_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a JSON file upload or JSON body payload must be provided."
        )

    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json", encoding="utf-8") as tmp:
        tmp.write(json_str)
        tmp_path = tmp.name

    target_account = account_id or 1  # Fallback to default account if not specified

    try:
        result = ingest_expenses_json(
            file_path=tmp_path,
            company_id=company_id,
            account_id=target_account,
            session=db,
        )
        return result
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post(
    "/{company_id}/accounts/{account_id}/receipts",
    response_model=IngestionResult,
    summary="Import receipt image (OCR)",
    description="Uploads a receipt image (JPG, PNG) for OCR processing and transaction creation.",
)
async def import_receipt_image(
    company_id: int,
    account_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _validate_company_and_account(company_id, account_id, db)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format. Allowed formats: JPG, JPEG, PNG, BMP, TIFF."
        )

    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = ingest_receipt_image(
            image_path=tmp_path,
            company_id=company_id,
            account_id=account_id,
            session=db,
        )
        return result
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
