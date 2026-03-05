"""Unit tests for app/service/auth.py — DB calls are mocked."""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.auth import LoginRequest, TenantRegistrationRequest
from app.service.auth import login_tenant, register_tenant


@pytest.fixture()
def mock_db():
    return MagicMock()


@pytest.fixture()
def reg_request():
    return TenantRegistrationRequest(
        name="Test Tenant",
        admin_name="Admin",
        admin_email="admin@test.com",
        admin_password="StrongPass1!",
    )


# ---------- register_tenant ----------

class TestRegisterTenant:
    @patch("app.service.auth.generate_unique_slug", return_value="test-tenant")
    @patch("app.service.auth.create_tenant")
    @patch("app.service.auth.create_user")
    @patch("app.service.auth.hash_password", return_value="hashed")
    @patch("app.service.auth.create_access_token")
    def test_returns_token_and_tenant_id(
        self,
        mock_token,
        _mock_hash,
        mock_create_user,
        mock_create_tenant,
        _mock_slug,
        mock_db,
        reg_request,
    ):
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_create_tenant.return_value = MagicMock(id=tenant_id)
        mock_create_user.return_value = MagicMock(id=user_id)
        mock_token.return_value = MagicMock(access_token="tok", token_type="bearer")

        result = register_tenant(reg_request, db=mock_db)

        assert result.tenant_id == tenant_id
        assert result.access_token == "tok"
        assert result.token_type == "bearer"

    @patch("app.service.auth.generate_unique_slug", return_value="test-tenant")
    @patch("app.service.auth.create_tenant")
    @patch("app.service.auth.create_user")
    @patch("app.service.auth.hash_password", return_value="hashed")
    @patch("app.service.auth.create_access_token")
    def test_creates_tenant_and_user(
        self,
        mock_token,
        _mock_hash,
        mock_create_user,
        mock_create_tenant,
        _mock_slug,
        mock_db,
        reg_request,
    ):
        mock_create_tenant.return_value = MagicMock(id=uuid.uuid4())
        mock_create_user.return_value = MagicMock(id=uuid.uuid4())
        mock_token.return_value = MagicMock(access_token="t", token_type="bearer")

        register_tenant(reg_request, db=mock_db)

        mock_create_tenant.assert_called_once()
        mock_create_user.assert_called_once()

    @patch("app.service.auth.generate_unique_slug", return_value="test-tenant")
    @patch("app.service.auth.create_tenant")
    @patch("app.service.auth.create_user")
    @patch("app.service.auth.hash_password", return_value="hashed")
    @patch("app.service.auth.create_access_token")
    def test_hashes_password_before_storing(
        self,
        mock_token,
        mock_hash,
        mock_create_user,
        mock_create_tenant,
        _mock_slug,
        mock_db,
        reg_request,
    ):
        mock_create_tenant.return_value = MagicMock(id=uuid.uuid4())
        mock_create_user.return_value = MagicMock(id=uuid.uuid4())
        mock_token.return_value = MagicMock(access_token="t", token_type="bearer")

        register_tenant(reg_request, db=mock_db)

        mock_hash.assert_called_once_with(reg_request.admin_password)
        _, kwargs = mock_create_user.call_args
        assert kwargs["password_hash"] == "hashed"


# ---------- login_tenant ----------

class TestLoginTenant:
    def test_invalid_email_raises_value_error(self, mock_db):
        tenant = MagicMock(id=uuid.uuid4())
        with patch("app.service.auth.get_user_by_email", return_value=None):
            with pytest.raises(ValueError, match="Invalid email or password"):
                login_tenant(
                    mock_db,
                    LoginRequest(email="no@one.com", password="pw"),
                    tenant,
                )

    def test_wrong_password_raises_value_error(self, mock_db):
        user = MagicMock(password_hash="hashed")
        tenant = MagicMock(id=uuid.uuid4())
        with patch("app.service.auth.get_user_by_email", return_value=user):
            with patch("app.service.auth.verify_password", return_value=False):
                with pytest.raises(ValueError, match="Invalid email or password"):
                    login_tenant(
                        mock_db,
                        LoginRequest(email="u@x.com", password="wrong"),
                        tenant,
                    )

    def test_success_returns_access_token(self, mock_db):
        user = MagicMock(id=uuid.uuid4(), password_hash="hashed")
        tenant = MagicMock(id=uuid.uuid4())
        with patch("app.service.auth.get_user_by_email", return_value=user):
            with patch("app.service.auth.verify_password", return_value=True):
                with patch("app.service.auth.create_access_token") as mock_token:
                    mock_token.return_value = MagicMock(access_token="tok123", token_type="bearer")
                    result = login_tenant(
                        mock_db,
                        LoginRequest(email="u@x.com", password="correct"),
                        tenant,
                    )
        assert result.access_token == "tok123"
        assert result.token_type == "bearer"

    def test_success_creates_token_with_correct_claims(self, mock_db):
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        user = MagicMock(id=user_id, password_hash="hashed")
        tenant = MagicMock(id=tenant_id)

        with patch("app.service.auth.get_user_by_email", return_value=user):
            with patch("app.service.auth.verify_password", return_value=True):
                with patch("app.service.auth.create_access_token") as mock_token:
                    mock_token.return_value = MagicMock(access_token="t", token_type="bearer")
                    login_tenant(
                        mock_db,
                        LoginRequest(email="u@x.com", password="correct"),
                        tenant,
                    )
                    call_args = mock_token.call_args[1]["token_claims"]
                    assert call_args.tenant_id == tenant_id
                    assert call_args.user_id == user_id
