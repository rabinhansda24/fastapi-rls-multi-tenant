"""Unit tests for app/utils/slug.py — no database required."""
from unittest.mock import MagicMock

from app.utils.slug import generate_unique_slug, slugyfy


# ---------- slugyfy (pure function) ----------

def test_slugyfy_lowercases():
    assert slugyfy("Hello World") == "hello-world"


def test_slugyfy_removes_special_chars():
    assert slugyfy("Acme Corp.") == "acme-corp"


def test_slugyfy_already_slug():
    assert slugyfy("my-tenant") == "my-tenant"


def test_slugyfy_numbers_kept():
    assert slugyfy("Tenant 42") == "tenant-42"


def test_slugyfy_empty_string():
    assert slugyfy("") == ""


# ---------- generate_unique_slug (mocked DB) ----------

def _db_returning(existing_slugs: list[str]) -> MagicMock:
    """Return a mock DB session whose execute() simulates slug uniqueness checks."""
    call_count = 0
    checked: list[str] = []

    def _execute(stmt):
        nonlocal call_count
        result = MagicMock()
        # We can't inspect the stmt easily, so track by call order
        # generate_unique_slug calls is_slug_unique once per candidate
        slug_candidate = slugyfy.__module__  # just to capture closure; unused
        result.scalar_one_or_none.return_value = (
            MagicMock() if call_count < len(existing_slugs) else None
        )
        call_count += 1
        return result

    mock_db = MagicMock()
    mock_db.execute.side_effect = _execute
    return mock_db


def test_generate_unique_slug_when_no_collision():
    mock_db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    slug = generate_unique_slug(mock_db, "Acme Corp")
    assert slug == "acme-corp"
    assert mock_db.execute.call_count == 1


def test_generate_unique_slug_appends_counter_on_collision():
    call_count = 0

    def _execute(stmt):
        nonlocal call_count
        r = MagicMock()
        # First call: slug taken; second call: slug-1 available
        r.scalar_one_or_none.return_value = MagicMock() if call_count == 0 else None
        call_count += 1
        return r

    mock_db = MagicMock()
    mock_db.execute.side_effect = _execute

    slug = generate_unique_slug(mock_db, "Acme Corp")
    assert slug == "acme-corp-1"
    assert mock_db.execute.call_count == 2


def test_generate_unique_slug_increments_until_unique():
    call_count = 0

    def _execute(stmt):
        nonlocal call_count
        r = MagicMock()
        # First two slugs taken, third available
        r.scalar_one_or_none.return_value = MagicMock() if call_count < 2 else None
        call_count += 1
        return r

    mock_db = MagicMock()
    mock_db.execute.side_effect = _execute

    slug = generate_unique_slug(mock_db, "Acme Corp")
    assert slug == "acme-corp-2"
