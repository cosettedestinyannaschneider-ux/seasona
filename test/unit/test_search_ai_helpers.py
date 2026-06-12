from __future__ import annotations

import pytest
from fastapi import HTTPException
from openai import APITimeoutError

from app.models.enums import MerchantAuditStatus, ProductStatus, UserStatus
from app.schemas.search import ProductSearchSort
from app.services.ai import service as ai_service
from app.services.ai.service import _parse_llm_payload
from app.services.search.service import (
    _base_meili_filter,
    _filter_expression,
    _normalize_query,
    _quote_filter_string,
    _sort_expression,
)


pytestmark = pytest.mark.unit


def test_search_payload_helpers_build_expected_filters_and_sorting() -> None:
    assert _normalize_query("  tomato  ") == "tomato"
    assert _quote_filter_string('A "quoted" value') == '"A \\"quoted\\" value"'
    assert _filter_expression(["a = 1", "", "b = 2"]) == "a = 1 AND b = 2"
    assert _sort_expression(ProductSearchSort.PRICE_ASC) == ["min_price:asc"]

    filters = _base_meili_filter(require_stock=True)

    assert f'status = "{ProductStatus.ONLINE.value}"' in filters
    assert f'merchant_audit_status = "{MerchantAuditStatus.APPROVED.value}"' in filters
    assert f'seller_status = "{UserStatus.ACTIVE.value}"' in filters
    assert "stock_total > 0" in filters


def test_parse_llm_payload_normalizes_items_and_rejects_bad_json() -> None:
    parsed = _parse_llm_payload(
        '{"status":"success","reply":"","items":[" tomato ","egg","tomato","beef","pork","fish","rice"]}'
    )

    assert parsed == {
        "status": "success",
        "reply": "",
        "items": ["tomato", "egg", "beef", "pork", "fish", "rice"],
    }

    with pytest.raises(HTTPException) as invalid_json:
        _parse_llm_payload("{not json")
    assert invalid_json.value.status_code == 502

    with pytest.raises(HTTPException) as invalid_status:
        _parse_llm_payload('{"status":"done","items":[]}')
    assert invalid_status.value.status_code == 502


def test_extract_ingredients_maps_llm_timeout_to_gateway_timeout(monkeypatch: pytest.MonkeyPatch, test_settings) -> None:
    class FakeCompletions:
        def create(self, **kwargs):
            _ = kwargs
            raise APITimeoutError(request=None)

    class FakeClient:
        chat = type("Chat", (), {"completions": FakeCompletions()})()

    class FakeSession:
        id = 1

    class FakeDb:
        def execute(self, statement):
            _ = statement
            return self

        def scalars(self):
            return self

        def all(self):
            return []

    monkeypatch.setattr(ai_service, "get_settings", lambda: test_settings.model_copy(update={"llm_model": "test-model"}))
    monkeypatch.setattr(ai_service, "get_llm_client", lambda: FakeClient())

    with pytest.raises(HTTPException) as exc_info:
        ai_service.extract_ingredients(FakeDb(), FakeSession(), "番茄炒蛋")

    assert exc_info.value.status_code == 504
    assert exc_info.value.detail == "LLM provider request timed out."
