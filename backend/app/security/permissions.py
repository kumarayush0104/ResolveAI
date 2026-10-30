from fastapi import HTTPException, status
from backend.app.db.models import User, Case, Order


def require_case_access(case: Case, user: User) -> None:
    """Enforce object-level access control on cases.
    - Buyer: can ONLY view and act on cases where case.buyer_id == user.id
    - Seller / Admin: can view and act on merchant cases
    Raises 403 Forbidden on violation.
    """
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    if user.role == "buyer":
        if case.buyer_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Buyers can only access their own cases",
            )
    elif user.role in ("seller", "admin"):
        # Merchant roles have access to merchant cases
        return
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Unknown user role",
        )


def require_order_access(order: Order, user: User) -> None:
    """Enforce object-level access control on orders.
    - Buyer: can ONLY access orders where order.user_id == user.id
    - Seller / Admin: have merchant access to all orders
    Raises 403 Forbidden on violation.
    """
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if user.role == "buyer":
        if order.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Buyers can only access their own orders",
            )
    elif user.role in ("seller", "admin"):
        return
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Unknown user role",
        )
