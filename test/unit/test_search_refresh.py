from __future__ import annotations

import pytest

from app.services.search import service as search_service


pytestmark = pytest.mark.unit


class FakeRedis:
    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired
        self.calls: list[tuple[str, str, bool, int]] = []

    def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        self.calls.append((key, value, nx, ex))
        return self.acquired


def test_review_search_refresh_uses_redis_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    redis_client = FakeRedis(acquired=True)
    upsert_calls: list[tuple[object, int]] = []
    monkeypatch.setattr(search_service, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(
        search_service,
        "upsert_product_search_document",
        lambda db, spu_id: upsert_calls.append((db, spu_id)) or True,
    )

    assert search_service.upsert_product_search_document_for_review_if_due(
        object(),
        7,
        cooldown_seconds=60,
    )
    assert redis_client.calls == [("seasona:search:review-refresh:7", "1", True, 60)]
    assert len(upsert_calls) == 1

    redis_client.acquired = False
    assert not search_service.upsert_product_search_document_for_review_if_due(
        object(),
        7,
        cooldown_seconds=60,
    )
    assert len(upsert_calls) == 1


def test_review_search_refresh_falls_back_when_redis_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upsert_calls: list[int] = []
    monkeypatch.setattr(search_service, "get_redis_client", lambda: None)
    monkeypatch.setattr(
        search_service,
        "upsert_product_search_document",
        lambda db, spu_id: upsert_calls.append(spu_id) or True,
    )

    assert search_service.upsert_product_search_document_for_review_if_due(object(), 8)
    assert upsert_calls == [8]


def test_background_review_refresh_opens_and_closes_own_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSession:
        closed = False

        def close(self) -> None:
            self.closed = True

    session = FakeSession()
    refresh_calls: list[tuple[object, int, int]] = []

    monkeypatch.setattr("app.db.session.get_session_factory", lambda: lambda: session)
    monkeypatch.setattr(
        search_service,
        "upsert_product_search_document_for_review_if_due",
        lambda db, spu_id, *, cooldown_seconds: refresh_calls.append(
            (db, spu_id, cooldown_seconds)
        )
        or True,
    )

    assert search_service.refresh_product_search_document_for_review_if_due(9, cooldown_seconds=30)
    assert session.closed
    assert refresh_calls == [(session, 9, 30)]
