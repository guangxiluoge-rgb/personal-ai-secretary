from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.billing import _complete_stripe_renewal


def _query_chain(first_value):
    query = MagicMock()
    query.filter.return_value.first.return_value = first_value
    return query


def test_stripe_renewal_extends_entitlement_to_invoice_period_end():
    db = MagicMock()
    db.query.side_effect = [
        _query_chain(None),
        _query_chain(SimpleNamespace(expires_at=datetime(2026, 10, 1, 0, 0))),
    ]
    order = SimpleNamespace(id=7, user_id=11, product_id="pro_monthly", currency="usd")
    period_end = int(datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc).timestamp())
    invoice = {
        "payment_intent": "pi_renewal_1",
        "amount_paid": 999,
        "currency": "usd",
        "lines": {"data": [{"period": {"end": period_end}}]},
    }

    with patch("app.api.billing.grant") as grant:
        assert _complete_stripe_renewal(db, order, invoice, "evt_renewal_1") is True

    grant.assert_called_once_with(
        db,
        11,
        "pro",
        source="stripe",
        expires_at=datetime(2026, 11, 1, 0, 0),
    )
    db.add.assert_called_once()
    db.commit.assert_called()


def test_stripe_renewal_is_idempotent_by_payment_id():
    db = MagicMock()
    db.query.side_effect = [_query_chain(SimpleNamespace(id=1))]
    order = SimpleNamespace(id=7, user_id=11, product_id="pro_monthly", currency="usd")
    invoice = {"payment_intent": "pi_renewal_duplicate"}

    with patch("app.api.billing.grant") as grant:
        assert _complete_stripe_renewal(db, order, invoice, "evt_duplicate") is False

    grant.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()
