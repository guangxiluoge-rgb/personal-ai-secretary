from app.services.life_os import _risk_advice, _risk_matches


def test_risk_rules_detect_urgent_transfer_and_fee():
    matches = _risk_matches("对方催我马上转账，还要先交保证金。")
    categories = {item[0] for item in matches}
    assert "urgent_transfer" in categories
    assert "guarantee_fee" in categories
    assert _risk_advice("urgent_transfer").startswith("先暂停付款")


def test_risk_rules_detect_credentials_request():
    matches = _risk_matches("对方让我提供验证码和密码。")
    categories = {item[0] for item in matches}
    assert "impersonation" in categories
