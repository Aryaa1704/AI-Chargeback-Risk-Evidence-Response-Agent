"""Database-backed customer investigation endpoints."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.customer import Customer
from app.models.dispute import Dispute
from app.models.transaction import Transaction
from app.schemas.api import CustomerHistoryResponse, DisputeResponse, SafeId, TransactionListItem

router = APIRouter(prefix="/customers", tags=["customers"])


def _customer_or_404(db: Session, customer_id: str) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.get("/{customer_id}/history", response_model=CustomerHistoryResponse, summary="Get a customer's synthetic transaction history")
def customer_history(customer_id: SafeId, db: Annotated[Session, Depends(get_db)]) -> CustomerHistoryResponse:
    """Return database-derived transactional aggregates and the customer's transactions."""
    _customer_or_404(db, customer_id)
    transactions = db.scalars(select(Transaction).where(Transaction.customer_id == customer_id).order_by(Transaction.created_at.desc())).all()
    total_amount = sum((row.amount for row in transactions), Decimal("0"))
    disputed_count = db.scalar(select(func.count(func.distinct(Dispute.transaction_id))).where(Dispute.customer_id == customer_id)) or 0
    count = len(transactions)
    return CustomerHistoryResponse(customer_id=customer_id, transaction_count=count, total_amount=total_amount, average_amount=(total_amount / count if count else Decimal("0")), disputed_transaction_count=disputed_count, transactions=[TransactionListItem.model_validate(row) for row in transactions])


@router.get("/{customer_id}/disputes", response_model=list[DisputeResponse], summary="Get a customer's synthetic dispute history")
def customer_disputes(customer_id: SafeId, db: Annotated[Session, Depends(get_db)]) -> list[DisputeResponse]:
    """Return only dispute records stored in the synthetic demo database."""
    _customer_or_404(db, customer_id)
    rows = db.scalars(select(Dispute).where(Dispute.customer_id == customer_id).order_by(Dispute.created_at.desc())).all()
    return [DisputeResponse.model_validate(row) for row in rows]
