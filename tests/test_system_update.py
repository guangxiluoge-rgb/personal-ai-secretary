from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_system_version_endpoint():
    response = client.get('/api/system/version')
    assert response.status_code == 200
    body = response.json()
    assert body['version']
    assert body['service']


def test_mobile_page_injects_update_checker():
    response = client.get('/mobile')
    assert response.status_code == 200
    assert 'dataset.appVersion=' in response.text
    assert 'src="/update.js"' in response.text
