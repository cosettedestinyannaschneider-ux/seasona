from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.enums import MerchantAuditStatus, ProductStatus, UserStatus
from app.schemas.search import ProductSearchSort
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
