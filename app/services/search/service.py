from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi import HTTPException, status
from sqlalchemy import case, cast, func, select
from sqlalchemy.types import DateTime

from app.core.config import get_settings
from app.models.enums import MerchantAuditStatus, ProductStatus, ReviewStatus, UserStatus
from app.models.product import (
    ProductCategory,
    ProductImage,
    ProductReview,
    ProductSku,
    ProductSpu,
    ProductTraceability,
)
from app.models.user import MerchantProfile, UserAccount
from app.schemas.search import (
    ProductSearchCard,
    ProductSearchResponse,
    ProductSearchSku,
    ProductSearchSort,
    ProductSearchSource,
)


SEARCH_INDEX_NAME = "seasona_products"
MEILI_REQUEST_TIMEOUT_SECONDS = 8
MEILI_SEARCHABLE_ATTRIBUTES = [
    "name",
    "category_name",
    "origin_place",
    "sku_text",
    "merchant_shop_name",
    "trace_text",
    "description",
]
MEILI_FILTERABLE_ATTRIBUTES = [
    "status",
    "merchant_audit_status",
    "seller_status",
    "category_active",
    "category_id",
    "merchant_id",
    "origin_place",
    "stock_total",
]
MEILI_SORTABLE_ATTRIBUTES = [
    "average_rating",
    "min_price",
    "max_price",
    "stock_total",
    "created_at_ts",
]
MEILI_DISPLAYED_ATTRIBUTES = ["*"]
MEILI_DOCUMENT_TEMPLATE = (
    "商品名称：{{doc.name}}\n"
    "分类：{{doc.category_name}}\n"
    "产地：{{doc.origin_place}}\n"
    "规格：{{doc.sku_text}}\n"
    "商家：{{doc.merchant_shop_name}}\n"
    "追溯：{{doc.trace_text}}\n"
    "描述：{{doc.description}}"
)


def _normalize_query(query: str | None) -> str:
    return (query or "").strip()


def _enum_value(value: Any) -> str:
    return getattr(value, "value", value)


def _timestamp_value(value: Any) -> int | None:
    if value is None:
        return None
    return int(value.timestamp())


def _discoverable_product_filters() -> list[Any]:
    return [
        ProductSpu.deleted_at.is_(None),
        ProductSpu.status == ProductStatus.ONLINE,
        MerchantProfile.audit_status == MerchantAuditStatus.APPROVED,
        UserAccount.status == UserStatus.ACTIVE,
        ProductCategory.is_active.is_(True),
    ]


def _sku_stats_subquery():
    return (
        select(
            ProductSku.spu_id.label("spu_id"),
            func.min(ProductSku.price).label("min_price"),
            func.max(ProductSku.price).label("max_price"),
            func.coalesce(func.sum(ProductSku.stock_available), 0).label("stock_total"),
        )
        .group_by(ProductSku.spu_id)
        .subquery()
    )


def _image_count_subquery():
    return (
        select(
            ProductImage.spu_id.label("spu_id"),
            func.count(ProductImage.id).label("image_count"),
        )
        .group_by(ProductImage.spu_id)
        .subquery()
    )


def _review_stats_subquery():
    return (
        select(
            ProductReview.spu_id.label("spu_id"),
            func.avg(ProductReview.rating).label("average_rating"),
            func.count(ProductReview.id).label("review_count"),
        )
        .where(ProductReview.status == ReviewStatus.VISIBLE)
        .group_by(ProductReview.spu_id)
        .subquery()
    )


def _product_card_statement():
    sku_stats = _sku_stats_subquery()
    image_stats = _image_count_subquery()
    review_stats = _review_stats_subquery()
    min_price_col = func.coalesce(sku_stats.c.min_price, Decimal("0.00"))
    max_price_col = func.coalesce(sku_stats.c.max_price, Decimal("0.00"))
    stock_total_col = func.coalesce(sku_stats.c.stock_total, 0)
    review_count_col = func.coalesce(review_stats.c.review_count, 0)

    created_at_col = cast(ProductSpu.created_at, DateTime(timezone=True))
    updated_at_col = cast(ProductSpu.updated_at, DateTime(timezone=True))
    statement = (
        select(
            ProductSpu,
            created_at_col.label("spu_created_at"),
            updated_at_col.label("spu_updated_at"),
            MerchantProfile.shop_name.label("shop_name"),
            ProductCategory.name.label("category_name"),
            min_price_col.label("min_price"),
            max_price_col.label("max_price"),
            stock_total_col.label("stock_total"),
            func.coalesce(image_stats.c.image_count, 0).label("image_count"),
            review_stats.c.average_rating.label("average_rating"),
            review_count_col.label("review_count"),
        )
        .join(MerchantProfile, ProductSpu.merchant_id == MerchantProfile.id)
        .join(UserAccount, MerchantProfile.user_id == UserAccount.id)
        .join(ProductCategory, ProductSpu.category_id == ProductCategory.id)
        .outerjoin(sku_stats, sku_stats.c.spu_id == ProductSpu.id)
        .outerjoin(image_stats, image_stats.c.spu_id == ProductSpu.id)
        .outerjoin(review_stats, review_stats.c.spu_id == ProductSpu.id)
    )
    return statement, sku_stats, min_price_col, max_price_col, stock_total_col


def _select_skus_by_spu_ids(db: Any, spu_ids: Sequence[int]) -> dict[int, list[ProductSearchSku]]:
    if not spu_ids:
        return {}
    rows = db.execute(
        select(ProductSku)
        .where(ProductSku.spu_id.in_(spu_ids))
        .order_by(ProductSku.price.asc(), ProductSku.id.asc())
    ).scalars().all()
    grouped: dict[int, list[ProductSearchSku]] = {}
    for sku in rows:
        grouped.setdefault(sku.spu_id, []).append(
            ProductSearchSku(
                sku_id=sku.id,
                spec_name=sku.spec_name,
                unit=sku.unit,
                price=sku.price,
                original_price=sku.original_price,
                stock_available=sku.stock_available,
                stock_locked=sku.stock_locked,
            )
        )
    return grouped


def _trace_text_from_row(traceability: ProductTraceability | None) -> str:
    if traceability is None:
        return ""
    parts = [
        traceability.trace_code,
        traceability.farm_name,
        str(traceability.harvest_date) if traceability.harvest_date else "",
        traceability.inspection_result,
        traceability.cold_chain_info,
    ]
    if traceability.trace_steps_json:
        for step in traceability.trace_steps_json:
            if isinstance(step, dict):
                parts.append(
                    " ".join(
                        str(step.get(key) or "")
                        for key in ("title", "content", "happened_at")
                    )
                )
            else:
                parts.append(str(step))
    return " ".join(item for item in parts if item)


def _row_to_search_document(db: Any, row: Any) -> dict[str, Any]:
    spu: ProductSpu = row.ProductSpu
    skus = _select_skus_by_spu_ids(db, [spu.id]).get(spu.id, [])
    traceability = db.execute(
        select(ProductTraceability).where(ProductTraceability.spu_id == spu.id)
    ).scalar_one_or_none()
    created_at = getattr(row, "spu_created_at", spu.created_at)
    updated_at = getattr(row, "spu_updated_at", spu.updated_at)
    sku_text = " ".join(
        " ".join(str(item or "") for item in [sku.spec_name, sku.unit]).strip()
        for sku in skus
    )
    return {
        "id": spu.id,
        "name": spu.name,
        "description": spu.description or "",
        "origin_place": spu.origin_place or "",
        "merchant_id": spu.merchant_id,
        "merchant_shop_name": row.shop_name or "",
        "category_id": spu.category_id,
        "category_name": row.category_name or "",
        "sku_text": sku_text,
        "trace_text": _trace_text_from_row(traceability),
        "min_price": float(row.min_price or 0),
        "max_price": float(row.max_price or 0),
        "stock_total": int(row.stock_total or 0),
        "average_rating": float(row.average_rating or 0),
        "review_count": int(row.review_count or 0),
        "status": _enum_value(spu.status),
        "merchant_audit_status": MerchantAuditStatus.APPROVED.value,
        "seller_status": UserStatus.ACTIVE.value,
        "category_active": True,
        "created_at_ts": _timestamp_value(created_at),
        "updated_at_ts": _timestamp_value(updated_at),
    }


def _meili_index_name() -> str:
    settings = get_settings()
    return settings.meilisearch_index or SEARCH_INDEX_NAME


def _meili_index_path() -> str:
    return f"/indexes/{quote(_meili_index_name(), safe='')}"


def _embedding_endpoint() -> str:
    settings = get_settings()
    base_url = settings.embedding_base_url.rstrip("/")
    if base_url.endswith("/embeddings"):
        return base_url
    return f"{base_url}/embeddings"


def _has_embedder_config() -> bool:
    settings = get_settings()
    return bool(
        settings.meilisearch_embedder
        and settings.embedding_api_key
        and settings.embedding_base_url
        and settings.embedding_model
    )


def _meili_settings_payload() -> dict[str, Any]:
    settings_payload: dict[str, Any] = {
        "displayedAttributes": MEILI_DISPLAYED_ATTRIBUTES,
        "searchableAttributes": MEILI_SEARCHABLE_ATTRIBUTES,
        "filterableAttributes": MEILI_FILTERABLE_ATTRIBUTES,
        "sortableAttributes": MEILI_SORTABLE_ATTRIBUTES,
    }
    settings = get_settings()
    if _has_embedder_config():
        settings_payload["embedders"] = {
            settings.meilisearch_embedder: {
                "source": "rest",
                "url": _embedding_endpoint(),
                "apiKey": settings.embedding_api_key,
                "request": {
                    "model": settings.embedding_model,
                    "input": "{{text}}",
                },
                "response": {
                    "data": [
                        {
                            "embedding": "{{embedding}}",
                        }
                    ],
                },
                "documentTemplate": MEILI_DOCUMENT_TEMPLATE,
            }
        }
    return settings_payload


def _meili_request(
    method: str,
    path: str,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    *,
    required: bool = True,
    not_found_none: bool = False,
) -> dict[str, Any] | None:
    settings = get_settings()
    base_url = settings.meilisearch_url.rstrip("/")
    if not base_url:
        if required:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Meilisearch is not configured.",
            )
        return None

    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if settings.meilisearch_api_key:
        headers["Authorization"] = f"Bearer {settings.meilisearch_api_key}"

    request = Request(
        f"{base_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=MEILI_REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read()
    except HTTPError as exc:
        if not_found_none and exc.code == 404:
            return None
        raw_detail = exc.read().decode("utf-8", errors="ignore")
        if required:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Meilisearch request failed: {raw_detail or exc.reason}",
            ) from exc
        return None
    except (TimeoutError, URLError) as exc:
        if required:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Meilisearch is unavailable.",
            ) from exc
        return None

    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _task_uid(task: dict[str, Any] | None) -> int | None:
    if not task:
        return None
    uid = task.get("taskUid", task.get("uid"))
    return int(uid) if uid is not None else None


def _ensure_search_index(*, required: bool = True) -> list[int]:
    task_uids: list[int] = []
    exists = _meili_request("GET", _meili_index_path(), required=required, not_found_none=True)
    if exists is None:
        task = _meili_request(
            "POST",
            "/indexes",
            {"uid": _meili_index_name(), "primaryKey": "id"},
            required=required,
        )
        uid = _task_uid(task)
        if uid is not None:
            task_uids.append(uid)

    settings_task = _meili_request(
        "PATCH",
        f"{_meili_index_path()}/settings",
        _meili_settings_payload(),
        required=required,
    )
    uid = _task_uid(settings_task)
    if uid is not None:
        task_uids.append(uid)
    return task_uids


def _base_meili_filter(*, require_stock: bool = False) -> list[str]:
    filters = [
        f'status = "{ProductStatus.ONLINE.value}"',
        f'merchant_audit_status = "{MerchantAuditStatus.APPROVED.value}"',
        f'seller_status = "{UserStatus.ACTIVE.value}"',
        "category_active = true",
    ]
    if require_stock:
        filters.append("stock_total > 0")
    return filters


def _quote_filter_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _filter_expression(filters: Sequence[str]) -> str:
    return " AND ".join(filter(None, filters))


def _sort_expression(sort_by: ProductSearchSort) -> list[str] | None:
    if sort_by == ProductSearchSort.RELEVANCE:
        return ["average_rating:desc", "created_at_ts:desc"]
    if sort_by == ProductSearchSort.NEWEST:
        return ["created_at_ts:desc"]
    if sort_by == ProductSearchSort.PRICE_ASC:
        return ["min_price:asc"]
    if sort_by == ProductSearchSort.PRICE_DESC:
        return ["max_price:desc"]
    if sort_by == ProductSearchSort.STOCK_DESC:
        return ["stock_total:desc"]
    return None


def _hybrid_payload(semantic_ratio: float) -> dict[str, Any] | None:
    settings = get_settings()
    if semantic_ratio <= 0 or not _has_embedder_config():
        return None
    return {
        "semanticRatio": semantic_ratio,
        "embedder": settings.meilisearch_embedder,
    }


def _search_meili(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_search_index(required=True)
    return _meili_request(
        "POST",
        f"{_meili_index_path()}/search",
        payload,
        required=True,
    ) or {}


def upsert_product_search_document(db: Any, spu_id: int) -> bool:
    spu = db.get(ProductSpu, spu_id)
    if spu is None:
        return False

    statement, _, _, _, _ = _product_card_statement()
    row = db.execute(
        statement.where(ProductSpu.id == spu_id, *_discoverable_product_filters())
    ).first()
    if row is None:
        return remove_product_search_document(spu_id)

    document = _row_to_search_document(db, row)
    try:
        _ensure_search_index(required=False)
        result = _meili_request(
            "POST",
            f"{_meili_index_path()}/documents",
            [document],
            required=False,
        )
        return result is not None
    except Exception:
        return False


def remove_product_search_document(spu_id: int) -> bool:
    try:
        result = _meili_request(
            "DELETE",
            f"{_meili_index_path()}/documents/{spu_id}",
            required=False,
        )
        return result is not None
    except Exception:
        return False


def upsert_product_search_document_for_review_if_due(
    db: Any,
    spu_id: int,
    *,
    cooldown_seconds: int = 300,
) -> bool:
    settings = get_settings()
    if not settings.redis_url:
        return upsert_product_search_document(db, spu_id)

    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        key = f"seasona:search:review-refresh:{spu_id}"
        acquired = client.set(key, "1", nx=True, ex=cooldown_seconds)
    except Exception:
        return upsert_product_search_document(db, spu_id)

    if not acquired:
        return False
    return upsert_product_search_document(db, spu_id)


def sync_merchant_search_documents(db: Any, merchant_id: int) -> int:
    spu_ids = db.execute(
        select(ProductSpu.id).where(ProductSpu.merchant_id == merchant_id)
    ).scalars().all()
    synced = 0
    for spu_id in spu_ids:
        if upsert_product_search_document(db, spu_id):
            synced += 1
    return synced


def sync_category_search_documents(db: Any, category_id: int) -> int:
    spu_ids = db.execute(
        select(ProductSpu.id).where(ProductSpu.category_id == category_id)
    ).scalars().all()
    synced = 0
    for spu_id in spu_ids:
        if upsert_product_search_document(db, spu_id):
            synced += 1
    return synced


def _rows_to_cards(
    db: Any,
    rows: Sequence[Any],
    *,
    scores: dict[int, float] | None = None,
    match_source: str | None = None,
) -> list[ProductSearchCard]:
    scores = scores or {}
    spu_ids = [row.ProductSpu.id for row in rows]
    skus_by_spu = _select_skus_by_spu_ids(db, spu_ids)
    cards: list[ProductSearchCard] = []

    for row in rows:
        spu: ProductSpu = row.ProductSpu
        skus = skus_by_spu.get(spu.id, [])
        default_sku = skus[0] if skus else None
        cards.append(
            ProductSearchCard(
                spu_id=spu.id,
                name=spu.name,
                description=spu.description,
                origin_place=spu.origin_place,
                cover_image_url=spu.cover_image_url,
                merchant_id=spu.merchant_id,
                merchant_shop_name=row.shop_name,
                category_id=spu.category_id,
                category_name=row.category_name,
                min_price=row.min_price,
                max_price=row.max_price,
                stock_total=int(row.stock_total or 0),
                average_rating=float(row.average_rating) if row.average_rating is not None else None,
                review_count=int(row.review_count or 0),
                default_sku_id=default_sku.sku_id if default_sku else None,
                default_sku_unit=default_sku.unit if default_sku else None,
                skus=skus,
                score=scores.get(spu.id),
                match_source=match_source,
                match_sources=[match_source] if match_source else [],
                created_at=row.spu_created_at,
                updated_at=row.spu_updated_at,
            )
        )
    return cards


def get_product_cards_by_spu_ids(
    db: Any,
    spu_ids: Sequence[int],
    *,
    scores: dict[int, float] | None = None,
    match_source: str | None = None,
    online_only: bool = True,
) -> list[ProductSearchCard]:
    unique_ids = list(dict.fromkeys(spu_ids))
    if not unique_ids:
        return []

    order_case = case({spu_id: idx for idx, spu_id in enumerate(unique_ids)}, value=ProductSpu.id)
    statement, _, _, _, _ = _product_card_statement()
    statement = statement.where(ProductSpu.id.in_(unique_ids)).order_by(order_case)
    if online_only:
        statement = statement.where(*_discoverable_product_filters())
    rows = db.execute(statement).all()
    return _rows_to_cards(db, rows, scores=scores, match_source=match_source)


def _cards_from_hits(
    db: Any,
    hits: Sequence[dict[str, Any]],
    *,
    match_source: str,
) -> list[ProductSearchCard]:
    spu_ids: list[int] = []
    scores: dict[int, float] = {}
    for hit in hits:
        raw_id = hit.get("id") or hit.get("spu_id")
        if raw_id is None:
            continue
        spu_id = int(raw_id)
        spu_ids.append(spu_id)
        score = hit.get("_rankingScore")
        if score is not None:
            scores[spu_id] = float(score)
    return get_product_cards_by_spu_ids(
        db,
        spu_ids,
        scores=scores,
        match_source=match_source,
    )


def search_products(
    db: Any,
    *,
    query: str = "",
    category_id: int | None = None,
    origin_place: str | None = None,
    in_stock_only: bool = False,
    sort_by: ProductSearchSort = ProductSearchSort.RELEVANCE,
    page: int = 1,
    page_size: int = 20,
) -> ProductSearchResponse:
    query = _normalize_query(query)
    settings = get_settings()
    filters = _base_meili_filter(require_stock=in_stock_only)
    if category_id is not None:
        filters.append(f"category_id = {category_id}")
    if origin_place:
        filters.append(f"origin_place = {_quote_filter_string(origin_place.strip())}")

    payload: dict[str, Any] = {
        "q": query,
        "filter": _filter_expression(filters),
        "page": page,
        "hitsPerPage": page_size,
        "showRankingScore": True,
        "locales": ["zh"],
    }
    hybrid = _hybrid_payload(settings.meilisearch_home_semantic_ratio)
    if hybrid is not None:
        payload["hybrid"] = hybrid
    sort = _sort_expression(sort_by)
    if sort is not None:
        payload["sort"] = sort

    response = _search_meili(payload)
    hits = response.get("hits") or []
    total = response.get("totalHits", response.get("estimatedTotalHits", len(hits)))
    return ProductSearchResponse(
        items=_cards_from_hits(db, hits, match_source="meilisearch"),
        total=int(total or 0),
        page=page,
        page_size=page_size,
        query=query,
        source=ProductSearchSource.MEILISEARCH,
    )


def search_products_for_ai_ingredient(
    db: Any,
    ingredient: str,
    *,
    limit: int = 5,
) -> list[ProductSearchCard]:
    ingredient = _normalize_query(ingredient)
    if not ingredient:
        return []

    settings = get_settings()
    payload: dict[str, Any] = {
        "q": ingredient,
        "filter": _filter_expression(_base_meili_filter(require_stock=True)),
        "limit": limit,
        "showRankingScore": True,
        "rankingScoreThreshold": settings.meilisearch_ai_ranking_score_threshold,
        "locales": ["zh"],
    }
    hybrid = _hybrid_payload(settings.meilisearch_ai_semantic_ratio)
    if hybrid is not None:
        payload["hybrid"] = hybrid

    response = _search_meili(payload)
    cards = _cards_from_hits(
        db,
        response.get("hits") or [],
        match_source="hybrid" if hybrid is not None else "meilisearch",
    )
    for card in cards:
        card.match_sources = ["meilisearch"]
        if hybrid is not None:
            card.match_sources.append("hybrid")
    return cards


def _iter_search_documents(db: Any) -> list[dict[str, Any]]:
    rows = db.execute(
        _product_card_statement()[0]
        .where(*_discoverable_product_filters())
        .order_by(ProductSpu.id.asc())
    ).all()
    return [_row_to_search_document(db, row) for row in rows]


def rebuild_search_index(db: Any) -> tuple[str, int, int, list[int]]:
    task_uids = _ensure_search_index(required=True)
    delete_task = _meili_request(
        "DELETE",
        f"{_meili_index_path()}/documents",
        required=True,
    )
    uid = _task_uid(delete_task)
    if uid is not None:
        task_uids.append(uid)

    documents = _iter_search_documents(db)
    if documents:
        add_task = _meili_request(
            "POST",
            f"{_meili_index_path()}/documents",
            documents,
            required=True,
        )
        uid = _task_uid(add_task)
        if uid is not None:
            task_uids.append(uid)
    return _meili_index_name(), len(documents), len(documents), task_uids
