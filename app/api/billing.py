import base64
import hashlib
import json
import time
import uuid
from urllib.parse import urlencode

import httpx
import stripe
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
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
    if not key:
        raise HTTPException(503, "Stripe is not configured")
    stripe.api_key = key

def _cny_price(db: Session, product_id: str) -> int:
    value = get_setting(db, f"payment_cny_{product_id}_price_minor", "")
    if value:
        try:
            return int(value)
        except ValueError:
            raise HTTPException(500, f"invalid CNY price for {product_id}")
    defaults = {"pro_monthly": 69, "health_pro_monthly": 129, "premium_monthly": 199}
    return defaults.get(product_id, 0)

def _new_order(db: Session, user_id: int, product: Product, amount_minor: int, currency: str) -> Order:
    order = Order(order_no=uuid.uuid4().hex, user_id=user_id, product_id=product.product_id, amount_minor=amount_minor, currency=currency, status="pending")
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

def _wechat_signature(method: str, path: str, body: str, timestamp: str, nonce: str, private_key_pem: str) -> str:
    message = f"{timestamp}\n{nonce}\n{body}\n".encode()
    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode()

def _alipay_sign(params: dict[str, str], private_key_pem: str) -> str:
    canonical = "&".join(f"{k}={params[k]}" for k in sorted(params) if params[k] is not None)
    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    signature = key.sign(canonical.encode(), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode()

@router.get("/products")
def products(db: Session = Depends(get_db)):
    ensure_products(db)
    return [{"product_id": p.product_id, "name": p.name, "price_minor": p.price_minor, "currency": p.currency, "interval": p.interval, "enabled": p.enabled} for p in db.query(Product).filter(Product.enabled.is_(True)).all()]

@router.get("/methods")
def payment_methods(db: Session = Depends(get_db)):
    return {
        "stripe": bool(get_setting(db, "stripe_secret_key", settings.stripe_secret_key)),
        "wechat": get_setting(db, "wechat_enabled", "false").lower() == "true" and bool(get_setting(db, "wechat_mch_id")),
        "alipay": get_setting(db, "alipay_enabled", "false").lower() == "true" and bool(get_setting(db, "alipay_app_id")),
    }

@router.post("/checkout")
def checkout(product_id: str, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    ensure_products(db)
    product = db.query(Product).filter(Product.product_id == product_id, Product.enabled.is_(True)).first()
    if not product:
        raise HTTPException(404, "product not found")
    stripe_client(db)
    if not product.stripe_price_id:
        raise HTTPException(503, "Stripe price ID is not configured for this product")
    order = _new_order(db, user_id, product, product.price_minor, product.currency)
    session = stripe.checkout.Session.create(mode="subscription", line_items=[{"price": product.stripe_price_id, "quantity": 1}], success_url=settings.stripe_success_url, cancel_url=settings.stripe_cancel_url, metadata={"order_id": str(order.id), "user_id": str(user_id), "product_id": product.product_id})
    return {"provider": "stripe", "order_no": order.order_no, "checkout_url": session.url}

@router.post("/wechat/native")
async def wechat_native(product_id: str, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    if get_setting(db, "wechat_enabled", "false").lower() != "true":
        raise HTTPException(503, "WeChat Pay is disabled")
    app_id = get_setting(db, "wechat_app_id"); mch_id = get_setting(db, "wechat_mch_id")
    serial_no = get_setting(db, "wechat_serial_no"); private_key = get_setting(db, "wechat_private_key")
    notify_url = get_setting(db, "wechat_notify_url")
    if not all([app_id, mch_id, serial_no, private_key, notify_url]):
        raise HTTPException(503, "WeChat Pay configuration is incomplete")
    product = db.query(Product).filter(Product.product_id == product_id, Product.enabled.is_(True)).first()
    if not product: raise HTTPException(404, "product not found")
    amount = _cny_price(db, product_id)
    order = _new_order(db, user_id, product, amount, "cny")
    body = {"appid": app_id, "mchid": mch_id, "description": product.name, "out_trade_no": order.order_no, "notify_url": notify_url, "amount": {"total": amount, "currency": "CNY"}}
    body_text = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    timestamp = str(int(time.time())); nonce = uuid.uuid4().hex
    signature = _wechat_signature("POST", "/v3/pay/transactions/native", body_text, timestamp, nonce, private_key)
    headers = {"Authorization": f'WECHATPAY2-SHA256-RSA2048 mchid="{mch_id}",nonce_str="{nonce}",timestamp="{timestamp}",serial_no="{serial_no}",signature="{signature}"', "Accept": "application/json", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post("https://api.mch.weixin.qq.com/v3/pay/transactions/native", content=body_text.encode(), headers=headers)
    if response.status_code >= 400:
        order.status = "payment_create_failed"; db.commit()
        raise HTTPException(response.status_code, "WeChat Pay order creation failed")
    data = response.json()
    return {"provider": "wechat", "order_no": order.order_no, "code_url": data.get("code_url")}

@router.post("/alipay/page")
def alipay_page(product_id: str, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    if get_setting(db, "alipay_enabled", "false").lower() != "true":
        raise HTTPException(503, "Alipay is disabled")
    app_id = get_setting(db, "alipay_app_id"); private_key = get_setting(db, "alipay_private_key")
    notify_url = get_setting(db, "alipay_notify_url"); return_url = get_setting(db, "alipay_return_url")
    if not all([app_id, private_key, notify_url]):
        raise HTTPException(503, "Alipay configuration is incomplete")
    product = db.query(Product).filter(Product.product_id == product_id, Product.enabled.is_(True)).first()
    if not product: raise HTTPException(404, "product not found")
    amount_minor = _cny_price(db, product_id)
    order = _new_order(db, user_id, product, amount_minor, "cny")
    params = {"app_id": app_id, "method": "alipay.trade.page.pay", "format": "JSON", "return_url": return_url, "charset": "utf-8", "sign_type": "RSA2", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "version": "1.0", "notify_url": notify_url, "biz_content": json.dumps({"out_trade_no": order.order_no, "product_code": "FAST_INSTANT_TRADE_PAY", "total_amount": f"{amount_minor / 100:.2f}", "subject": product.name}, separators=(",", ":"), ensure_ascii=False)}
    params["sign"] = _alipay_sign(params, private_key)
    gateway = get_setting(db, "alipay_gateway_url", "https://openapi.alipay.com/gateway.do")
    return {"provider": "alipay", "order_no": order.order_no, "pay_url": gateway + "?" + urlencode(params)}

@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body(); sig = request.headers.get("stripe-signature")
    secret = get_setting(db, "stripe_webhook_secret", settings.stripe_webhook_secret)
    if not secret: raise HTTPException(503, "Stripe webhook secret is not configured")
    try: event = stripe.Webhook.construct_event(payload, sig, secret)
    except Exception: raise HTTPException(400, "invalid Stripe webhook")
    event_id = event.get("id")
    if db.query(Payment).filter(Payment.raw_event_id == event_id).first(): return {"received": True}
    obj = event["data"]["object"]; metadata = obj.get("metadata") or {}; order_id = int(metadata.get("order_id", 0) or 0)
    order = db.query(Order).filter(Order.id == order_id).first() if order_id else None
    if event["type"] in {"checkout.session.completed", "invoice.paid"} and order:
        order.status = "paid"; grant(db, order.user_id, order.product_id.removesuffix("_monthly"), source="stripe", expires_at=None)
        db.add(Payment(order_id=order.id, provider="stripe", provider_payment_id=obj.get("id", ""), raw_event_id=event_id, status="paid", amount_minor=order.amount_minor, currency=order.currency)); db.commit()
    elif event["type"] in {"customer.subscription.deleted", "invoice.payment_failed"} and order:
        order.status = "payment_failed" if event["type"].endswith("failed") else "cancelled"; revoke(db, order.user_id, order.product_id.removesuffix("_monthly")); db.commit()
    return {"received": True}
