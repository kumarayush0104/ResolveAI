from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Product, User
from backend.app.db.session import get_db
from backend.app.security.auth import get_current_user

router = APIRouter(prefix="/catalog", tags=["catalog"])


class ProductRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    price: float = Field(..., ge=0.01, le=100000)


def _product_dict(product: Product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "active": product.active,
    }


def _require_seller(user: User) -> None:
    if user.role not in ("seller", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seller role required")


@router.get("/items")
async def list_products(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    products = (await session.execute(
        select(Product).where(Product.active.is_(True)).order_by(Product.created_at, Product.name)
    )).scalars().all()
    return [_product_dict(product) for product in products]


@router.post("/items", status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    _require_seller(current_user)
    product = Product(
        seller_id=current_user.id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        price=float(Decimal(str(payload.price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
    )
    if not product.name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Product name is required")
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return _product_dict(product)


@router.patch("/items/{product_id}")
async def update_product(
    product_id: str,
    payload: ProductRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    _require_seller(current_user)
    product = (await session.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if product is None or (current_user.role != "admin" and product.seller_id != current_user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    name = payload.name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Product name is required")
    product.name = name
    product.description = payload.description.strip()
    product.price = float(Decimal(str(payload.price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    await session.commit()
    await session.refresh(product)
    return _product_dict(product)
