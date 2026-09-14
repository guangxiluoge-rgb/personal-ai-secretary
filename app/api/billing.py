import base64
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import stripe
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user_id
from app.db import get_db
from app.models import Order, Product, Payment, Entitlement
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
            amount = int(value)
        except ValueError:
            raise HTTPException(500, f"invalid CNY price for {product_id}")
    else:
        amount = {"pro_monthly": 69, "health_pro_monthly": 129, "premium_monthly": 199}.get(product_id, 0)
    if amount <= 0:
        raise HTTPException(500, f"invalid CNY price for {product_id}")
    return amount


def _new_order(db: Session, user_id: int, product: Product, amount_minor: int, currency: str) -> Order:
    order = Order(order_no=uuid.uuid4().hex, user_id=user_id, product_id=product.product_id, amount_minor=amount_minor, currency=currency, status="pending")
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _monthly_expiry() -> datetime:
    return datetime.utcnow() + timedelta(days=30)


def _complete_order(db: Session, order: Order, provider: str, provider_payment_id: str, raw_event_id: str | None, paid_amount_minor: int | None = None, expires_at: datetime | None = None):
    if not provider_payment_id:
        raise HTTPException(400, "missing provider payment ID")
    if order.status == "paid":
        return False
    if paid_amount_minor is not None and paid_amount_minor != order.amount_minor:
        raise HTTPException(400, "payment amount mismatch")
    existing = db.query(Payment).filter(Payment.provider == provider, Payment.provider_payment_id == provider_payment_id).first()
    if existing:
        order.status = "paid"
        db.commit()
        return False
    order.status = "paid"
    feature = order.product_id.removesuffix("_monthly")
    grant(db, order.user_id, feature, source=provider, expires_at=expires_at or _monthly_expiry())
    db.add(Payment(order_id=order.id, provider=provider, provider_payment_id=provider_payment_id, raw_event_id=raw_event_id, status="paid", amount_minor=order.amount_minor, currency=order.currency))
    db.commit()
    return True


def _extend_entitlement(db: Session, user_id: int, feature: str, source: str, expires_at: datetime | None = None):
    row = db.query(Entitlement).filter(Entitlement.user_id == user_id, Entitlement.feature == feature).first()
    current = row.expires_at if row and row.expires_at and row.expires_at > datetime.utcnow() else datetime.utcnow()
    grant(db, user_id, feature, source=source, expires_at=expires_at or (current + timedelta(days=30)))


def _wechat_signature(body: str, timestamp: str, nonce: str, private_key_pem: str) -> str:
    message = f"{timestamp}\n{nonce}\n{body}\n".encode()
    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    return base64.b64encode(key.sign(message, padding.PKCS1v15(), hashes.SHA256())).decode()


def _verify_wechat_notification(request: Request, body: str, platform_public_key_pem: str):
    timestamp = request.headers.get("Wechatpay-Timestamp", "")
    nonce = request.headers.get("Wechatpay-Nonce", "")
    signature = request.headers.get("Wechatpay-Signature", "")
    if not timestamp or not nonce or not signature:
        raise HTTPException(400, "missing WeChat payment signature headers")
    try:
        if abs(int(time.time()) - int(timestamp)) > 300:
            raise HTTPException(400, "stale WeChat payment notification")
        key = serialization.load_pem_public_key(platform_public_key_pem.encode())
        key.verify(base64.b64decode(signature), f"{timestamp}\n{nonce}\n{body}\n".encode(), padding.PKCS1v15(), hashes.SHA256())
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "invalid WeChat payment signature")


def _decrypt_wechat_resource(resource: dict, api_v3_key: str) -> dict:
    if resource.get("algorithm") != "AEAD_AES_256_GCM":
        raise HTTPException(400, "unsupported WeChat notification encryption")
    try:
        key = api_v3_key.encode()
        if len(key) != 32:
            raise ValueError("APIv3 key must be 32 bytes")
        plaintext = AESGCM(key).decrypt(resource["nonce"].encode(), base64.b64decode(resource["ciphertext"]), resource.get("associated_data", "").encode())
        return json.loads(plaintext.decode())
    except Exception:
        raise HTTPException(400, "invalid WeChat notification encryption")


def _alipay_sign(params: dict[str, str], private_key_pem: str) -> str:
    canonical = "&".join(f"{k}={params[k]}" for k in sorted(params) if k not in {"sign", "sign_type"} and params[k] is not None)
    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    return base64.b64encode(key.sign(canonical.encode(), padding.PKCS1v15(), hashes.SHA256())).decode()


def _verify_alipay(params: dict[str, str], public_key_pem: str):
    sign = params.get("sign", "")
    if not sign:
        raise HTTPException(400, "missing Alipay signature")
    canonical = "&".join(f"{k}={params[k]}" for k in sorted(params) if k not in {"sign", "sign_type"} and params[k] is not None)
    try:
        key = serialization.load_pem_public_key(public_key_pem.encode())
        key.verify(base64.b64decode(sign), canonical.encode(), padding.PKCS1v15(), hashes.SHA256())
    except Exception:
        raise HTTPException(400, "invalid Alipay notification signature")


@router.get("/products")
def products(db: Session = Depends(get_db)):
    ensure_products(db)
    return [{"product_id": p.product_id, "name": p.name, "price_minor": p.price_minor, "currency": p.currency, "interval": p.interval, "enabled": p.enabled} for p in db.query(Product).filter(Product.enabled.is_(True)).all()]


@router.get("/methods")
def payment_methods(db: Session = Depends(get_db)):
    return {
        "stripe": bool(get_setting(db, "stripe_secret_key", settings.stripe_secret_key)),
        "wechat": get_setting(db, "wechat_enabled", str(settings.wechat_enabled)).lower() == "true" and bool(get_setting(db, "wechat_mch_id", settings.wechat_mch_id)),
        "alipay": get_setting(db, "alipay_enabled", str(settings.alipay_enabled)).lower() == "true" and bool(get_setting(db, "alipay_app_id", settings.alipay_app_id)),
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
    success_url = get_setting(db, "stripe_success_url", settings.stripe_success_url)
    cancel_url = get_setting(db, "stripe_cancel_url", settings.stripe_cancel_url)
    session = stripe.checkout.Session.create(mode="subscription", line_items=[{"price": product.stripe_price_id, "quantity": 1}], success_url=success_url, cancel_url=cancel_url, metadata={"order_id": str(order.id), "user_id": str(user_id), "product_id": product.product_id})
    return {"provider": "stripe", "order_no": order.order_no, "checkout_url": session.url}


@router.post("/wechat/native")
async def wechat_native(product_id: str, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    if get_setting(db, "wechat_enabled", str(settings.wechat_enabled)).lower() != "true":
        raise HTTPException(503, "WeChat Pay is disabled")
    app_id = get_setting(db, "wechat_app_id", settings.wechat_app_id)
    mch_id = get_setting(db, "wechat_mch_id", settings.wechat_mch_id)
    serial_no = get_setting(db, "wechat_serial_no", settings.wechat_serial_no)
    private_key = get_setting(db, "wechat_private_key", settings.wechat_private_key)
    notify_url = get_setting(db, "wechat_notify_url", settings.wechat_notify_url)
    if not all([app_id, mch_id, serial_no, private_key, notify_url]):
        raise HTTPException(503, "WeChat Pay configuration is incomplete")
    product = db.query(Product).filter(Product.product_id == product_id, Product.enabled.is_(True)).first()
    if not product:
        raise HTTPException(404, "product not found")
    amount = _cny_price(db, product_id)
    order = _new_order(db, user_id, product, amount, "CNY")
    body = {"appid": app_id, "mchid": mch_id, "description": product.name, "out_trade_no": order.order_no, "notify_url": notify_url, "amount": {"total": amount, "currency": "CNY"}}
    body_text = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    signature = _wechat_signature(body_text, timestamp, nonce, private_key)
    headers = {"Authorization": f'WECHATPAY2-SHA256-RSA2048 mchid="{mch_id}",nonce_str="{nonce}",timestamp="{timestamp}",serial_no="{serial_no}",signature="{signature}"', "Accept": "application/json", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post("https://api.mch.weixin.qq.com/v3/pay/transactions/native", content=body_text.encode(), headers=headers)
    if response.status_code >= 400:
        order.status = "payment_create_failed"
        db.commit()
        raise HTTPException(response.status_code, "WeChat Pay order creation failed")
    data = response.json()
    return {"provider": "wechat", "order_no": order.order_no, "code_url": data.get("code_url")}


@router.post("/alipay/page")
def alipay_page(product_id: str, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    if get_setting(db, "alipay_enabled", str(settings.alipay_enabled)).lower() != "true":
        raise HTTPException(503, "Alipay is disabled")
    app_id = get_setting(db, "alipay_app_id", settings.alipay_app_id)
    private_key = get_setting(db, "alipay_private_key", settings.alipay_private_key)
    notify_url = get_setting(db, "alipay_notify_url", settings.alipay_notify_url)
    return_url = get_setting(db, "alipay_return_url", settings.alipay_return_url)
    if not all([app_id, private_key, notify_url]):
        raise HTTPException(503, "Alipay configuration is incomplete")
    product = db.query(Product).filter(Product.product_id == product_id, Product.enabled.is_(True)).first()
    if not product:
        raise HTTPException(404, "product not found")
    amount_minor = _cny_price(db, product_id)
    order = _new_order(db, user_id, product, amount_minor, "CNY")
    params = {"app_id": app_id, "method": "alipay.trade.page.pay", "format": "JSON", "return_url": return_url, "charset": "utf-8", "sign_type": "RSA2", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "version": "1.0", "notify_url": notify_url, "biz_content": json.dumps({"out_trade_no": order.order_no, "product_code": "FAST_INSTANT_TRADE_PAY", "total_amount": f"{amount_minor / 100:.2f}", "subject": product.name}, separators=(",", ":"), ensure_ascii=False)}
    params["sign"] = _alipay_sign(params, private_key)
    gateway = get_setting(db, "alipay_gateway_url", settings.alipay_gateway_url)
    return {"provider": "alipay", "order_no": order.order_no, "pay_url": gateway + "?" + urlencode(params)}


@router.post("/wechat/webhook")
async def wechat_webhook(request: Request, db: Session = Depends(get_db)):
    body = (await request.body()).decode()
    public_key = get_setting(db, "wechat_platform_public_key", settings.wechat_platform_public_key)
    api_v3_key = get_setting(db, "wechat_api_v3_key", settings.wechat_api_v3_key)
    if not public_key or not api_v3_key:
        raise HTTPException(503, "WeChat webhook verification is not configured")
    _verify_wechat_notification(request, body, public_key)
    event = json.loads(body)
    notify_id = event.get("id") or uuid.uuid4().hex
    if db.query(Payment).filter(Payment.raw_event_id == f"wechat:{notify_id}").first():
        return {"code": "SUCCESS", "message": "成功"}
    resource = _decrypt_wechat_resource(event.get("resource") or {}, api_v3_key)
    if resource.get("trade_state") != "SUCCESS":
        return {"code": "SUCCESS", "message": "已接收"}
    order = db.query(Order).filter(Order.order_no == resource.get("out_trade_no")).first()
    if not order:
        raise HTTPException(404, "order not found")
    paid_amount = int(((resource.get("amount") or {}).get("total") or 0))
    _complete_order(db, order, "wechat", resource.get("transaction_id", ""), f"wechat:{notify_id}", paid_amount)
    return {"code": "SUCCESS", "message": "成功"}


@router.post("/alipay/webhook")
async def alipay_webhook(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    public_key = get_setting(db, "alipay_public_key", settings.alipay_public_key)
    if not public_key:
        raise HTTPException(503, "Alipay public key is not configured")
    _verify_alipay(form, public_key)
    trade_status = form.get("trade_status", "")
    if trade_status not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
        return "success"
    order = db.query(Order).filter(Order.order_no == form.get("out_trade_no")).first()
    if not order:
        raise HTTPException(404, "order not found")
    amount = int(round(float(form.get("total_amount", "0")) * 100))
    event_id = f"alipay:{form.get('notify_id') or form.get('trade_no') or uuid.uuid4().hex}"
    _complete_order(db, order, "alipay", form.get("trade_no", ""), event_id, amount)
    return "success"


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    secret = get_setting(db, "stripe_webhook_secret", settings.stripe_webhook_secret)
    if not secret:
        raise HTTPException(503, "Stripe webhook secret is not configured")
    try:
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except Exception:
        raise HTTPException(400, "invalid Stripe webhook")
    event_id = event.get("id")
    if db.query(Payment).filter(Payment.raw_event_id == event_id).first():
        return {"received": True}
    obj = event["data"]["object"]
    metadata = obj.get("metadata") or {}
    order_id = int(metadata.get("order_id", 0) or 0)
    order = db.query(Order).filter(Order.id == order_id).first() if order_id else None
    if event["type"] == "checkout.session.completed" and order:
        paid_amount = int(obj.get("amount_total") or order.amount_minor)
        _complete_order(db, order, "stripe", obj.get("id", ""), event_id, paid_amount)
    elif event["type"] == "invoice.paid":
        subscription_id = obj.get("subscription")
        if subscription_id:
            matched = db.query(Order).filter(Order.user_id == int(metadata.get("user_id", 0) or 0), Order.product_id == metadata.get("product_id", "")).order_by(Order.id.desc()).first() if metadata.get("user_id") and metadata.get("product_id") else None
            if matched:
                feature = matched.product_id.removesuffix("_monthly")
                period_end = (obj.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end") if obj.get("lines") else None)
                expires_at = datetime.fromtimestamp(period_end, tz=timezone.utc).replace(tzinfo=None) if period_end else None
                _extend_entitlement(db, matched.user_id, feature, "stripe", expires_at)
                db.commit()
    elif event["type"] == "customer.subscription.deleted" and order:
        order.status = "cancelled"
        revoke(db, order.user_id, order.product_id.removesuffix("_monthly"))
        db.commit()
    elif event["type"] == "invoice.payment_failed" and order:
        order.status = "payment_failed"
        db.commit()
    return {"received": True}
