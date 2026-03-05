def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_openapi_schema_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "paths" in data


def test_unauthenticated_cases_returns_401(client):
    response = client.get("/v1/cases/")
    assert response.status_code == 401


def test_register_and_login_smoke(client):
    reg_resp = client.post(
        "/v1/auth/register",
        json={
            "name": "Smoke Tenant",
            "admin_name": "Smoke Admin",
            "admin_email": "smoke@example.com",
            "admin_password": "SmokePass123!",
        },
    )
    assert reg_resp.status_code == 200
    body = reg_resp.json()
    assert "access_token" in body
    assert "tenant_id" in body

    login_resp = client.post(
        "/v1/auth/smoke-tenant/login",
        json={"email": "smoke@example.com", "password": "SmokePass123!"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()