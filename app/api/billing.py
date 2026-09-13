import uuid
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import get_current_user_id
from app.db import get_db
from app.models import Order, Product, Payment
from app.services.admin_service import get_setting
from app.services.entitlement_service import grant, revoke

router = APIRouter(prefix="/api/billing", tags=["billing"])

DEFAULT_PRODUCTS = [
    ("pro_monthly", "Pro", 999, "pro"),
    ("health_pro_monthly", "Health Pro", 1999, "health_pro"),
    ("premium_monthly", "Premium", 2999, "premium"),
]

def ensure_products(db: Session):
    for pid, name, price, feature in DEFAULT_PRODUCTS:
        row = db.query(Product).filter(Product.product_id == pid).first()
        configured = get_setting(db, f"product_{pid}_price_minor", str(price))
        if not row:
            row = Product(product_id=pid, name=name, price_minor=int(configured or price), currency="usd", interval="month", stripe_price_id=get_setting(db, f"stripe_price_{pid}", ""), enabled=True)
            db.add(row)
        else:
            row.price_minor = int(configured or row.price_minor)
            row.stripe_price_id = get_setting(db, f"stripe_price_{pid}", row.stripe_price_id)
    db.commit()

def stripe_client(db: Session):
    key = get_setting(db, "stripe_secret_key", settings.stripe_secret_key)
    if not key: raise HTTPException(503, "Stripe is not configured")
    stripe.api_key = key

@router.get("/products")
def products(db: Session = Depends(get_db)):
    ensure_products(db)
    return [{"product_id": p.product_id, "name": p.name, "price_minor": p.price_minor, "currency": p.currency, "interval": p.interval, "enabled": p.enabled} for p in db.query(Product).filter(Product.enabled.is_(True)).all()]

@router.post("/checkout")
def checkout(product_id: str, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    ensure_products(db); product = db.query(Product).filter(Product.product_id == product_id, Product.enabled.is_(True)).first()
    if not product: raise HTTPException(404, "product not found")
    stripe_client(db)
    if not product.stripe_price_id: raise HTTPException(503, "Stripe price ID is not configured for this product")
    order = Order(order_no=uuid.uuid4().hex, user_id=user_id, product_id=product.product_id, amount_minor=product.price_minor, currency=product.currency, status="pending")
    db.add(order); db.commit(); db.refresh(order)
    session = stripe.checkout.Session.create(mode="subscription", line_items=[{"price": product.stripe_price_id, "quantity": 1}], success_url=settings.stripe_success_url, cancel_url=settings.stripe_cancel_url, metadata={"order_id": str(order.id), "user_id": str(user_id), "product_id": product.product_id})
    return {"order_no": order.order_no, "checkout_url": session.url}

@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body(); sig = request.headers.get("stripe-signature")
    secret = get_setting(db, "stripe_webhook_secret", settings.stripe_webhook_secret)
    if not secret: raise HTTPException(503, "Stripe webhook secret is not configured")
    try: event = stripe.Webhook.construct_event(payload, sig, secret)
    except Exception: raise HTTPException(400, "invalid Stripe webhook")
    event_id = event.get("id")
    if db.query(Payment).filter(Payment.raw_event_id == event_id).first(): return {"received": True}
    obj = event["data"]["object"]
    metadata = obj.get("metadata") or {}
    order_id = int(metadata.get("order_id", 0) or 0)
    order = db.query(Order).filter(Order.id == order_id).first() if order_id else None
    if event["type"] in {"checkout.session.completed", "invoice.paid"} and order:
        order.status = "paid"; grant(db, order.user_id, order.product_id.removesuffix("_monthly"), source="stripe", expires_at=None)
        db.add(Payment(order_id=order.id, provider="stripe", provider_payment_id=obj.get("id", ""), raw_event_id=event_id, status="paid", amount_minor=order.amount_minor, currency=order.currency)); db.commit()
    elif event["type"] in {"customer.subscription.deleted", "invoice.payment_failed"} and order:
        order.status = "payment_failed" if event["type"].endswith("failed") else "cancelled"; revoke(db, order.user_id, order.product_id.removesuffix("_monthly"))
    return {"received": True}
