from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.db.models import User
from backend.app.paypal.transactions import search_transaction
from backend.app.security.auth import get_current_user

router = APIRouter(prefix="/paypal", tags=["transactions"])


@router.get("/transactions/{transaction_id}")
async def lookup_transaction(
    transaction_id: str,
    days_back: int = Query(30, ge=1, le=31, description="How far back to search (PayPal allows at most 31 days)"),
    current_user: User = Depends(get_current_user),
):
    """Look up one PayPal transaction (a capture ID is a transaction ID) in Transaction Search.

    Merchant tools only: this reads the merchant account's reporting data.
    S/P/D/V come back normalized as COMPLETED/PENDING/DENIED/REVERSED. "Not found" is reported as
    such and never as a failure, because reporting can lag by up to 3 hours.
    """
    if current_user.role not in ("seller", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden: merchant roles only")

    now = datetime.now(timezone.utc)
    result = await search_transaction(transaction_id, start=now - timedelta(days=days_back), end=now)
    return result.to_dict()
