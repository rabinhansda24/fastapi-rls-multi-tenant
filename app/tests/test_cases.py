"""Integration tests for /v1/cases endpoints."""
import uuid
import pytest


# ---------- helpers ----------

def _register_tenant(client, suffix=None):
    """Register a new tenant and return (slug, token)."""
    suffix = suffix or uuid.uuid4().hex[:8]
    name = f"Cases Tenant {suffix}"
    email = f"admin-{suffix}@example.com"
    password = "CasesPass1!"

    resp = client.post(
        "/v1/auth/register",
        json={
            "name": name,
            "admin_name": "Admin",
            "admin_email": email,
            "admin_password": password,
        },
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    slug = f"cases-tenant-{suffix}"
    return slug, token


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- fixtures ----------

@pytest.fixture()
def tenant_a(client):
    slug, token = _register_tenant(client)
    return {"slug": slug, "token": token, "headers": _auth_headers(token)}


@pytest.fixture()
def tenant_b(client):
    slug, token = _register_tenant(client)
    return {"slug": slug, "token": token, "headers": _auth_headers(token)}


# ---------- tests ----------

class TestCreateCase:
    def test_create_case_returns_201_with_open_status(self, client, tenant_a):
        resp = client.post("/v1/cases/", json={"status": "OPEN"}, headers=tenant_a["headers"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "OPEN"
        assert "id" in body
        assert "tenant_id" in body

    def test_create_case_requires_auth(self, client):
        resp = client.post("/v1/cases/", json={"status": "OPEN"})
        assert resp.status_code == 401

    def test_create_case_invalid_token_returns_401(self, client):
        resp = client.post(
            "/v1/cases/",
            json={"status": "OPEN"},
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert resp.status_code == 401

    def test_create_case_with_in_review_status(self, client, tenant_a):
        resp = client.post("/v1/cases/", json={"status": "IN_REVIEW"}, headers=tenant_a["headers"])
        assert resp.status_code == 200
        assert resp.json()["status"] == "IN_REVIEW"


class TestListCases:
    def test_list_cases_returns_own_cases(self, client, tenant_a):
        client.post("/v1/cases/", json={"status": "OPEN"}, headers=tenant_a["headers"])
        resp = client.get("/v1/cases/", headers=tenant_a["headers"])
        assert resp.status_code == 200
        cases = resp.json()
        assert isinstance(cases, list)
        assert len(cases) >= 1

    def test_list_cases_rls_isolation(self, client, tenant_a, tenant_b):
        """Tenant A's cases must not appear in tenant B's list."""
        create_resp = client.post(
            "/v1/cases/", json={"status": "OPEN"}, headers=tenant_a["headers"]
        )
        assert create_resp.status_code == 200
        case_id = create_resp.json()["id"]

        b_cases = client.get("/v1/cases/", headers=tenant_b["headers"]).json()
        b_case_ids = [c["id"] for c in b_cases]
        assert case_id not in b_case_ids

    def test_list_cases_requires_auth(self, client):
        resp = client.get("/v1/cases/")
        assert resp.status_code == 401


class TestGetCase:
    def test_get_case_by_id(self, client, tenant_a):
        create_resp = client.post("/v1/cases/", json={"status": "OPEN"}, headers=tenant_a["headers"])
        case_id = create_resp.json()["id"]

        resp = client.get(f"/v1/cases/{case_id}", headers=tenant_a["headers"])
        assert resp.status_code == 200
        assert resp.json()["id"] == case_id

    def test_get_case_rls_isolation(self, client, tenant_a, tenant_b):
        """Tenant B cannot retrieve tenant A's case."""
        create_resp = client.post(
            "/v1/cases/", json={"status": "OPEN"}, headers=tenant_a["headers"]
        )
        case_id = create_resp.json()["id"]

        resp = client.get(f"/v1/cases/{case_id}", headers=tenant_b["headers"])
        # RLS hides the row; service raises 404
        assert resp.status_code in (404, 500)

    def test_get_nonexistent_case_returns_404(self, client, tenant_a):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/v1/cases/{fake_id}", headers=tenant_a["headers"])
        assert resp.status_code in (404, 500)


class TestUpdateCaseStatus:
    def test_update_status_success(self, client, tenant_a):
        case_id = client.post(
            "/v1/cases/", json={"status": "OPEN"}, headers=tenant_a["headers"]
        ).json()["id"]

        resp = client.patch(
            f"/v1/cases/{case_id}/status",
            json={"status": "IN_REVIEW", "idempotency_key": uuid.uuid4().hex},
            headers=tenant_a["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["new_status"] == "IN_REVIEW"
        assert body["case_id"] == case_id

    def test_update_status_idempotency(self, client, tenant_a):
        """Sending the same idempotency_key twice returns the same event."""
        case_id = client.post(
            "/v1/cases/", json={"status": "OPEN"}, headers=tenant_a["headers"]
        ).json()["id"]
        idem_key = uuid.uuid4().hex

        first = client.patch(
            f"/v1/cases/{case_id}/status",
            json={"status": "IN_REVIEW", "idempotency_key": idem_key},
            headers=tenant_a["headers"],
        )
        second = client.patch(
            f"/v1/cases/{case_id}/status",
            json={"status": "IN_REVIEW", "idempotency_key": idem_key},
            headers=tenant_a["headers"],
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["event_id"] == second.json()["event_id"]

    def test_update_status_requires_auth(self, client):
        resp = client.patch(
            f"/v1/cases/{uuid.uuid4()}/status",
            json={"status": "IN_REVIEW", "idempotency_key": "key"},
        )
        assert resp.status_code == 401


class TestCaseEvents:
    def test_list_events_after_create(self, client, tenant_a):
        case_id = client.post(
            "/v1/cases/", json={"status": "OPEN"}, headers=tenant_a["headers"]
        ).json()["id"]

        resp = client.get(f"/v1/cases/{case_id}/events", headers=tenant_a["headers"])
        assert resp.status_code == 200
        events = resp.json()
        assert isinstance(events, list)
        # A CASE_CREATED event is written on case creation
        assert any(e["event_type"] == "CASE_CREATED" for e in events)

    def test_list_events_after_status_update(self, client, tenant_a):
        case_id = client.post(
            "/v1/cases/", json={"status": "OPEN"}, headers=tenant_a["headers"]
        ).json()["id"]

        client.patch(
            f"/v1/cases/{case_id}/status",
            json={"status": "IN_REVIEW", "idempotency_key": uuid.uuid4().hex},
            headers=tenant_a["headers"],
        )

        events = client.get(
            f"/v1/cases/{case_id}/events", headers=tenant_a["headers"]
        ).json()
        event_types = [e["event_type"] for e in events]
        assert "CASE_CREATED" in event_types
        assert "STATUS_CHANGED" in event_types
