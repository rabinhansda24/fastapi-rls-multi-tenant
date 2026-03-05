"""Unit tests for app/service/case.py — DB calls are mocked."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.domain.case_enum import CaseEventType, CaseStatus
from app.schemas.case import CaseCreate, CaseStatusUpdateRequest
from app.service.case import (
    create_new_case,
    get_all_cases,
    get_case_by_id,
    update_case_status,
)


@pytest.fixture()
def mock_db():
    return MagicMock()


@pytest.fixture()
def tenant_id():
    return uuid.uuid4()


@pytest.fixture()
def user_id():
    return uuid.uuid4()


# ---------- create_new_case ----------

class TestCreateNewCase:
    @patch("app.service.case.create_case_no_commit")
    @patch("app.service.case.create_case_event_no_commit")
    def test_returns_case_response(
        self, mock_event, mock_case, mock_db, tenant_id, user_id
    ):
        case_id = uuid.uuid4()
        fake_case = MagicMock()
        fake_case.id = case_id
        fake_case.tenant_id = tenant_id
        fake_case.created_by = user_id
        fake_case.status = CaseStatus.OPEN
        fake_case.created_at = "2024-01-01T00:00:00"
        mock_case.return_value = fake_case
        mock_event.return_value = MagicMock(id=uuid.uuid4())

        result = create_new_case(
            mock_db,
            case_in=CaseCreate(status=CaseStatus.OPEN),
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert result.id == case_id
        assert result.status == CaseStatus.OPEN
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(fake_case)

    @patch("app.service.case.create_case_no_commit")
    @patch("app.service.case.create_case_event_no_commit")
    def test_creates_case_created_event(
        self, mock_event, mock_case, mock_db, tenant_id, user_id
    ):
        fake_case = MagicMock(id=uuid.uuid4(), tenant_id=tenant_id, created_by=user_id,
                               status=CaseStatus.OPEN, created_at="2024-01-01")
        mock_case.return_value = fake_case
        mock_event.return_value = MagicMock(id=uuid.uuid4())

        create_new_case(
            mock_db,
            case_in=CaseCreate(status=CaseStatus.OPEN),
            tenant_id=tenant_id,
            created_by=user_id,
        )

        _, kwargs = mock_event.call_args
        assert kwargs["event_in"].event_type == CaseEventType.CASE_CREATED

    @patch("app.service.case.create_case_no_commit", side_effect=Exception("DB error"))
    def test_raises_http_exception_on_db_error(
        self, _mock_case, mock_db, tenant_id, user_id
    ):
        with pytest.raises(HTTPException) as exc_info:
            create_new_case(
                mock_db,
                case_in=CaseCreate(status=CaseStatus.OPEN),
                tenant_id=tenant_id,
                created_by=user_id,
            )
        assert exc_info.value.status_code == 500


# ---------- get_all_cases ----------

class TestGetAllCases:
    @patch("app.service.case.list_cases")
    def test_returns_list_of_cases(self, mock_list, mock_db):
        mock_list.return_value = [MagicMock(), MagicMock()]
        result = get_all_cases(mock_db)
        assert len(result) == 2

    @patch("app.service.case.list_cases", side_effect=Exception("DB error"))
    def test_raises_http_exception_on_db_error(self, _mock, mock_db):
        with pytest.raises(HTTPException) as exc_info:
            get_all_cases(mock_db)
        assert exc_info.value.status_code == 500


# ---------- get_case_by_id ----------

class TestGetCaseById:
    @patch("app.service.case.get_case")
    def test_returns_case_when_found(self, mock_get, mock_db):
        fake_case = MagicMock()
        mock_get.return_value = fake_case
        result = get_case_by_id(mock_db, case_id=uuid.uuid4())
        assert result is fake_case

    @patch("app.service.case.get_case", return_value=None)
    def test_raises_404_when_not_found(self, _mock, mock_db):
        with pytest.raises(HTTPException) as exc_info:
            get_case_by_id(mock_db, case_id=uuid.uuid4())
        assert exc_info.value.status_code == 404


# ---------- update_case_status ----------

class TestUpdateCaseStatus:
    def _make_request(self, status=CaseStatus.IN_REVIEW, key=None):
        return CaseStatusUpdateRequest(
            status=status,
            idempotency_key=key or uuid.uuid4().hex,
        )

    @patch("app.service.case.get_case_by_idempotency_key", return_value=None)
    @patch("app.service.case.get_case")
    @patch("app.service.case.update_case_status_no_commit")
    @patch("app.service.case.create_status_change_event_no_commit")
    def test_updates_status_and_returns_response(
        self,
        mock_event,
        mock_update,
        mock_get_case,
        mock_idem,
        mock_db,
        tenant_id,
        user_id,
    ):
        case_id = uuid.uuid4()
        event_id = uuid.uuid4()
        fake_case = MagicMock(id=case_id, status=CaseStatus.OPEN)
        mock_get_case.return_value = fake_case
        mock_event.return_value = MagicMock(
            id=event_id, event_type=CaseEventType.STATUS_CHANGED
        )

        result = update_case_status(
            mock_db,
            case_id=case_id,
            tenant_id=tenant_id,
            created_by=user_id,
            request=self._make_request(),
        )

        assert result.new_status == CaseStatus.IN_REVIEW
        assert result.event_id == event_id
        mock_db.commit.assert_called_once()

    @patch("app.service.case.get_case_by_idempotency_key")
    def test_idempotency_returns_existing_event(
        self, mock_idem, mock_db, tenant_id, user_id
    ):
        case_id = uuid.uuid4()
        event_id = uuid.uuid4()
        existing_event = MagicMock(
            id=event_id,
            event_type=CaseEventType.STATUS_CHANGED,
            payload={"new_status": "IN_REVIEW"},
        )
        mock_idem.return_value = existing_event

        result = update_case_status(
            mock_db,
            case_id=case_id,
            tenant_id=tenant_id,
            created_by=user_id,
            request=self._make_request(),
        )

        assert result.event_id == event_id
        assert result.new_status == CaseStatus.IN_REVIEW
        mock_db.commit.assert_not_called()

    @patch("app.service.case.get_case_by_idempotency_key", return_value=None)
    @patch("app.service.case.get_case", return_value=None)
    def test_raises_404_when_case_not_found(
        self, _mock_get, _mock_idem, mock_db, tenant_id, user_id
    ):
        with pytest.raises(HTTPException) as exc_info:
            update_case_status(
                mock_db,
                case_id=uuid.uuid4(),
                tenant_id=tenant_id,
                created_by=user_id,
                request=self._make_request(),
            )
        assert exc_info.value.status_code == 404
