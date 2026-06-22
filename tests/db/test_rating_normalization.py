import pytest

from backend.db.client_db import ClientWriteDatabase
from backend.utils.domain_exceptions import BadRequestError


def test_normalize_score_rounds_to_nearest_half():
    assert ClientWriteDatabase._normalize_score(8.3) == 8.5
    assert ClientWriteDatabase._normalize_score(8.2) == 8.0


def test_normalize_score_clamps_low_values():
    assert ClientWriteDatabase._normalize_score(-5) == 0.0


def test_normalize_score_clamps_high_values():
    assert ClientWriteDatabase._normalize_score(99) == 10.0


def test_normalize_score_rejects_none():
    with pytest.raises(BadRequestError):
        ClientWriteDatabase._normalize_score(None)