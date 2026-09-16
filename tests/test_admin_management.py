from app.api.admin import AdminCreateIn, AdminPasswordIn, StatusIn


def test_admin_create_requires_strong_minimum_password():
    assert AdminCreateIn(email="admin@example.com", password="abcdefgh").is_superadmin is False


def test_admin_password_and_status_schemas():
    assert AdminPasswordIn(password="abcdefgh").password == "abcdefgh"
    assert StatusIn(is_active=False).is_active is False
