"""Database-backed transaction investigation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.transaction import Transaction
from app.schemas.api import PageResponse, SafeId, SortDirection, TransactionDetailResponse, TransactionListItem, TransactionSortField

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=PageResponse, summary="List synthetic transactions")
def list_transactions(
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    customer_id: SafeId | None = None,
    status_filter: Annotated[str | None, Query(alias="status", min_length=1, max_length=40)] = None,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    sort_by: TransactionSortField = "created_at",
    sort_dir: SortDirection = "desc",
) -> PageResponse:
    """Return a searchable, paginated, filtered list sourced only from the synthetic database."""
    filters = []
    if customer_id:
        filters.append(Transaction.customer_id == customer_id)
    if status_filter:
        filters.append(Transaction.status == status_filter)
    if currency:
        filters.append(Transaction.currency == currency.upper())
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(Transaction.transaction_id.ilike(pattern), Transaction.customer_id.ilike(pattern), Transaction.merchant_id.ilike(pattern), Transaction.status.ilike(pattern)))
    total = db.scalar(select(func.count()).select_from(Transaction).where(*filters)) or 0
    sort_column = getattr(Transaction, sort_by)
    ordering = asc(sort_column) if sort_dir == "asc" else desc(sort_column)
    rows = db.scalars(select(Transaction).where(*filters).order_by(ordering, Transaction.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return PageResponse(items=[TransactionListItem.model_validate(row) for row in rows], page=page, page_size=page_size, total=total)


@router.get("/{transaction_id}", response_model=TransactionDetailResponse, summary="Get a synthetic transaction detail")
def get_transaction(transaction_id: SafeId, db: Annotated[Session, Depends(get_db)]) -> TransactionDetailResponse:
    """Return transaction detail with directly related database records, never generated evidence."""
    row = db.scalar(select(Transaction).options(joinedload(Transaction.customer), joinedload(Transaction.merchant), joinedload(Transaction.disputes)).where(Transaction.transaction_id == transaction_id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return TransactionDetailResponse(id=row.id, transaction_id=row.transaction_id, customer_id=row.customer_id, merchant_id=row.merchant_id, device_id=row.device_id, amount=row.amount, currency=row.currency, status=row.status, created_at=row.created_at, updated_at=row.updated_at, customer_email=row.customer.email, customer_name=row.customer.full_name, merchant_name=row.merchant.name, merchant_category=row.merchant.category, disputes_count=len(row.disputes))
