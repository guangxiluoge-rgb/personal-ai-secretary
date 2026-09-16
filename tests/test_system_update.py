def test_system_version_endpoint(client):
    response = client.get('/api/system/version')
    assert response.status_code == 200
    body = response.json()
    assert body['version']
    assert body['service']


def test_mobile_page_injects_update_checker(client):
    response = client.get('/mobile')
    assert response.status_code == 200
    assert 'data-app-version' in response.text
    assert 'src="/update.js"' in response.text
