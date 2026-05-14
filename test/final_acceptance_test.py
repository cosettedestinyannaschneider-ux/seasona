from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import sys
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi.testclient import TestClient
from sqlalchemy import func, select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from main import app
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models.enums import OrderStatus, UserRole, UserStatus, WalletBizType
from app.models.order import Order, OrderItem, RefundApplication
from app.models.product import ProductSku
from app.models.user import UserAccount
from app.models.wallet import WalletAccount, WalletLedger


settings = get_settings()
Session = get_session_factory()
client = TestClient(app, raise_server_exceptions=False)
stamp = datetime.now().strftime("%Y%m%d%H%M%S")
prefix = f"final{stamp}"
password = "password123"
results: list[dict] = []
external_notes: list[tuple] = []
ids: dict[str, int] = {}
tokens: dict[str, str] = {}


def log(name: str, ok: bool, detail: object = "", status_code: int | None = None, category: str = "core") -> None:
    results.append(
        {
            "name": name,
            "ok": bool(ok),
            "detail": str(detail)[:700],
            "status": status_code,
            "category": category,
        }
    )
    mark = "PASS" if ok else ("EXT" if category == "external" else "FAIL")
    extra = f" :: {status_code}" if status_code is not None else ""
    if detail:
        extra += f" :: {str(detail)[:220]}"
    print(f"[{mark}] {name}{extra}")


def auth(token: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


def response_body(resp):
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text[:500]}


def req(
    name: str,
    method: str,
    url: str,
    *,
    token: str | None = None,
    expected: tuple[int, ...] = (200,),
    category: str = "core",
    **kwargs,
):
    headers = kwargs.pop("headers", {}) or {}
    headers.update(auth(token))
    resp = client.request(method, url, headers=headers, **kwargs)
    body = response_body(resp)
    ok = resp.status_code in expected
    if not ok and category == "external" and resp.status_code in {502, 503, 504}:
        external_notes.append((name, resp.status_code, body))
        log(name, True, body, resp.status_code, "external")
    else:
        log(name, ok, body if not ok else "", resp.status_code, category)
    return resp, body


def must(name: str, method: str, url: str, **kwargs):
    resp, body = req(name, method, url, **kwargs)
    if resp.status_code not in kwargs.get("expected", (200,)):
        raise RuntimeError(f"{name} failed: {resp.status_code} {body}")
    return body


def seed_admin() -> str:
    username = f"{prefix}Admin"
    with Session.begin() as db:
        user = db.execute(
            select(UserAccount).where(
                UserAccount.role == UserRole.ADMIN,
                UserAccount.username == username,
            )
        ).scalar_one_or_none()
        if user is None:
            user = UserAccount(
                username=username,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                nickname="Final Admin",
                avatar_url=None,
                phone=None,
                email=None,
            )
            db.add(user)
            db.flush()
        ids["admin_user_id"] = user.id
    return username


def db_wallet(user_id: int) -> tuple[Decimal, Decimal, int]:
    with Session() as db:
        wallet = db.execute(
            select(WalletAccount).where(WalletAccount.user_id == user_id)
        ).scalar_one()
        return Decimal(wallet.available_balance), Decimal(wallet.frozen_balance), wallet.version


def db_sku(sku_id: int) -> tuple[int, int, int]:
    with Session() as db:
        sku = db.get(ProductSku, sku_id)
        return sku.stock_available, sku.stock_locked, sku.version


def db_order(order_id: int) -> tuple[str, bool, bool, bool]:
    with Session() as db:
        order = db.get(Order, order_id)
        return (
            order.status.value,
            bool(order.is_shipped),
            order.paid_at is not None,
            order.shipped_at is not None,
        )


def ledger_count(
    user_id: int,
    biz_type: WalletBizType | None = None,
    reference_type: str | None = None,
    reference_id: int | None = None,
) -> int:
    with Session() as db:
        wallet = db.execute(
            select(WalletAccount).where(WalletAccount.user_id == user_id)
        ).scalar_one()
        statement = select(func.count(WalletLedger.id)).where(
            WalletLedger.wallet_account_id == wallet.id
        )
        if biz_type:
            statement = statement.where(WalletLedger.biz_type == biz_type)
        if reference_type:
            statement = statement.where(WalletLedger.reference_type == reference_type)
        if reference_id:
            statement = statement.where(WalletLedger.reference_id == reference_id)
        return db.execute(statement).scalar_one()


def make_receiver(name: object) -> dict:
    return {
        "receiver_name": f"Buyer {name}",
        "receiver_phone": "13800000000",
        "province": "Zhejiang",
        "city": "Hangzhou",
        "district": "Xihu",
        "detail": f"{prefix} Road {name}",
    }


def add_cart_and_order(buyer_token: str, sku_id: int, name: object, qty: int = 1) -> dict:
    cart = must(
        f"cart add {name}",
        "POST",
        "/api/v1/cart/items",
        token=buyer_token,
        expected=(201,),
        json={"sku_id": sku_id, "quantity": qty, "selected": True},
    )
    item_id = [item["id"] for item in cart["items"] if item["sku_id"] == sku_id][-1]
    body = must(
        f"order create {name}",
        "POST",
        "/api/v1/orders",
        token=buyer_token,
        expected=(201,),
        json={
            "idempotency_key": f"{prefix}-order-{name}",
            "auto_pay": False,
            "cart_item_ids": [item_id],
            "receiver_snapshot": make_receiver(name),
        },
    )
    return body["orders"][0]


def pay_order(buyer_token: str, order_id: int, name: str) -> dict:
    return must(name, "POST", f"/api/v1/orders/{order_id}/pay", token=buyer_token)


def ship_order(seller_token: str, order_id: int, name: str) -> dict:
    return must(name, "POST", f"/api/v1/seller/orders/{order_id}/ship", token=seller_token)


def wait_meili_tasks(task_uids: list[int], timeout: int = 90) -> list[dict]:
    if not task_uids:
        return []
    base_url = settings.meilisearch_url.rstrip("/")
    headers = {"Accept": "application/json"}
    if settings.meilisearch_api_key:
        headers["Authorization"] = f"Bearer {settings.meilisearch_api_key}"
    deadline = time.time() + timeout
    output = []
    for uid in task_uids:
        last = None
        while time.time() < deadline:
            try:
                request = Request(f"{base_url}/tasks/{uid}", headers=headers, method="GET")
                with urlopen(request, timeout=8) as response:
                    last = json.loads(response.read().decode("utf-8"))
                if last.get("status") in {"succeeded", "failed", "canceled"}:
                    break
            except Exception as exc:
                last = {"status": "error", "error": str(exc)}
                break
            time.sleep(0.5)
        output.append(last or {"status": "timeout"})
    return output


def product_payload(name: str, stock: int, price: str = "8.80") -> dict:
    return {
        "category_id": ids["category_id"],
        "name": name,
        "description": f"{name} description tomato egg potato beef",
        "origin_place": f"{prefix} Origin",
        "cover_image_url": ids.get("product_image_url"),
        "skus": [
            {
                "spec_name": "500g pack",
                "unit": "pack",
                "price": price,
                "original_price": "9.90",
                "stock_available": stock,
            }
        ],
        "images": [
            {
                "image_url": ids.get("product_image_url"),
                "is_cover": True,
                "sort_order": 0,
            }
        ],
        "traceability": {
            "trace_code": f"TRACE-{name}",
            "farm_name": f"{prefix} Farm",
            "harvest_date": "2026-05-01",
            "inspection_result": "Passed",
            "cold_chain_info": "Normal",
            "trace_steps_json": [
                {"title": "Harvest", "content": "Picked", "happened_at": "2026-05-01"}
            ],
        },
    }


def run() -> None:
    req("root", "GET", "/")
    req("health", "GET", "/api/v1/health")
    req("openapi", "GET", "/api/v1/openapi.json")

    admin_username = seed_admin()
    tokens["admin"] = must(
        "admin login seeded",
        "POST",
        "/api/v1/auth/admin/login",
        json={"username": admin_username, "password": password},
    )["access_token"]

    buyer_username = f"{prefix}Buyer"
    buyer2_username = f"{prefix}BuyerX"
    seller_username = f"{prefix}Seller"
    reject_seller_username = f"{prefix}SellerR"

    buyer = must(
        "buyer register",
        "POST",
        "/api/v1/auth/buyer/register",
        expected=(201,),
        json={
            "username": buyer_username,
            "password": password,
            "register_method": "phone",
            "phone": "13" + stamp[-9:],
            "nickname": "Final Buyer",
        },
    )
    buyer2 = must(
        "buyer2 register",
        "POST",
        "/api/v1/auth/buyer/register",
        expected=(201,),
        json={
            "username": buyer2_username,
            "password": password,
            "register_method": "email",
            "email": f"{buyer2_username.lower()}@example.com",
        },
    )
    seller = must(
        "seller register",
        "POST",
        "/api/v1/auth/seller/register",
        expected=(201,),
        json={
            "shop_name": f"{prefix} Farm",
            "username": seller_username,
            "contact_name": "Owner",
            "phone": "14" + stamp[-9:],
            "password": password,
            "email": f"{seller_username.lower()}@example.com",
            "shop_description": "Final test seller",
        },
    )
    reject_seller = must(
        "reject seller register",
        "POST",
        "/api/v1/auth/seller/register",
        expected=(201,),
        json={
            "shop_name": f"{prefix} Reject Farm",
            "username": reject_seller_username,
            "contact_name": "Reject",
            "phone": "15" + stamp[-9:],
            "password": password,
            "email": f"{reject_seller_username.lower()}@example.com",
        },
    )
    tokens["buyer"] = must(
        "buyer login",
        "POST",
        "/api/v1/auth/buyer/login",
        json={"identifier": buyer_username, "password": password},
    )["access_token"]
    tokens["buyer2"] = must(
        "buyer2 login",
        "POST",
        "/api/v1/auth/buyer/login",
        json={"identifier": buyer2_username, "password": password},
    )["access_token"]
    tokens["seller"] = must(
        "seller login",
        "POST",
        "/api/v1/auth/seller/login",
        json={"identifier": seller_username, "password": password},
    )["access_token"]
    tokens["reject_seller"] = must(
        "reject seller login",
        "POST",
        "/api/v1/auth/seller/login",
        json={"identifier": reject_seller_username, "password": password},
    )["access_token"]
    ids["buyer_user_id"] = buyer["user"]["id"]
    ids["buyer2_user_id"] = buyer2["user"]["id"]
    ids["seller_user_id"] = seller["user"]["id"]
    ids["seller_merchant_id"] = seller["user"]["merchant_profile"]["id"]
    ids["reject_merchant_id"] = reject_seller["user"]["merchant_profile"]["id"]

    req("no token admin forbidden", "GET", "/api/v1/admin/users", expected=(401,))
    req("bad token forbidden", "GET", "/api/v1/auth/me", token="bad.token.value", expected=(401,))
    req("buyer cannot seller dashboard", "GET", "/api/v1/seller/dashboard", token=tokens["buyer"], expected=(403,))
    req("seller cannot buyer wallet", "GET", "/api/v1/orders/wallet", token=tokens["seller"], expected=(403,))
    req("buyer me", "GET", "/api/v1/auth/me", token=tokens["buyer"])
    req(
        "buyer me patch",
        "PATCH",
        "/api/v1/auth/me",
        token=tokens["buyer"],
        json={"nickname": f"{prefix} Nick", "avatar_url": "/media/avatars/final.png"},
    )
    logout_token = tokens["buyer2"]
    req("logout buyer2", "POST", "/api/v1/auth/logout", token=logout_token)
    req("logout token revoked", "GET", "/api/v1/auth/me", token=logout_token, expected=(401,))
    tokens["buyer2"] = must(
        "buyer2 relogin",
        "POST",
        "/api/v1/auth/buyer/login",
        json={"identifier": buyer2_username, "password": password},
    )["access_token"]

    audit_upload = req(
        "merchant audit image upload",
        "POST",
        "/api/v1/uploads/merchant-audit-images",
        token=tokens["seller"],
        expected=(201,),
        files={"file": ("audit.png", b"\\x89PNG\\r\\n\\x1a\\nfinal", "image/png")},
    )[1]
    req(
        "invalid audit upload type",
        "POST",
        "/api/v1/uploads/merchant-audit-images",
        token=tokens["seller"],
        expected=(400,),
        files={"file": ("bad.txt", b"bad", "text/plain")},
    )
    req("seller profile get", "GET", "/api/v1/seller/profile", token=tokens["seller"])
    req(
        "seller profile patch",
        "PATCH",
        "/api/v1/seller/profile",
        token=tokens["seller"],
        json={
            "shop_name": f"{prefix} Farm Updated",
            "shop_logo_url": audit_upload.get("image_url"),
            "shop_description": "Updated public shop",
        },
    )
    req(
        "seller audit materials patch",
        "PATCH",
        "/api/v1/seller/audit-materials",
        token=tokens["seller"],
        json={"audit_material_text": "final audit material", "audit_images_json": [audit_upload.get("image_url")]},
    )
    req("seller audit submit", "POST", "/api/v1/seller/audit-materials/submit", token=tokens["seller"])
    req("reject seller audit submit", "POST", "/api/v1/seller/audit-materials/submit", token=tokens["reject_seller"])
    req("admin merchants pending", "GET", "/api/v1/admin/merchants?status_filter=pending", token=tokens["admin"])
    req(
        "admin merchant reject route",
        "POST",
        f"/api/v1/admin/merchants/{ids['reject_merchant_id']}/reject",
        token=tokens["admin"],
        json={"reason": "reject route coverage"},
    )
    req(
        "admin merchant approve",
        "POST",
        f"/api/v1/admin/merchants/{ids['seller_merchant_id']}/approve",
        token=tokens["admin"],
        json={"reason": "approved for final test"},
    )
    req(
        "audit patch after approve rejected",
        "PATCH",
        "/api/v1/seller/audit-materials",
        token=tokens["seller"],
        expected=(400,),
        json={"audit_material_text": "should fail"},
    )
    product_upload = req(
        "product image upload",
        "POST",
        "/api/v1/uploads/images",
        token=tokens["seller"],
        expected=(201,),
        files={"file": ("product.png", b"\\x89PNG\\r\\n\\x1a\\nproduct", "image/png")},
    )[1]
    ids["product_image_url"] = product_upload.get("image_url")
    req(
        "invalid product upload type",
        "POST",
        "/api/v1/uploads/images",
        token=tokens["seller"],
        expected=(400,),
        files={"file": ("bad.txt", b"bad", "text/plain")},
    )

    category = must(
        "admin category create",
        "POST",
        "/api/v1/admin/categories",
        token=tokens["admin"],
        expected=(201,),
        json={"name": f"{prefix} Vegetables", "sort_order": 1, "is_active": True},
    )
    ids["category_id"] = category["id"]
    req("admin category patch", "PATCH", f"/api/v1/admin/categories/{ids['category_id']}", token=tokens["admin"], json={"sort_order": 2})
    req("admin categories list", "GET", "/api/v1/admin/categories", token=tokens["admin"])
    req("public categories list", "GET", "/api/v1/products/categories")

    main_product = must(
        "seller product create main",
        "POST",
        "/api/v1/seller/products",
        token=tokens["seller"],
        expected=(201,),
        json=product_payload(f"{prefix} Tomato", 120),
    )
    ids["spu_main"] = main_product["id"]
    ids["sku_main"] = main_product["skus"][0]["id"]
    rejected_product = must(
        "seller product create rejected",
        "POST",
        "/api/v1/seller/products",
        token=tokens["seller"],
        expected=(201,),
        json=product_payload(f"{prefix} Rejected Product", 20),
    )
    ids["spu_rejected"] = rejected_product["id"]
    offline_product = must(
        "seller product create offlinecycle",
        "POST",
        "/api/v1/seller/products",
        token=tokens["seller"],
        expected=(201,),
        json=product_payload(f"{prefix} Offline Cycle", 20),
    )
    ids["spu_offline"] = offline_product["id"]
    req("seller products list", "GET", "/api/v1/seller/products", token=tokens["seller"])
    req("seller product get", "GET", f"/api/v1/seller/products/{ids['spu_main']}", token=tokens["seller"])
    req("seller product update draft", "PATCH", f"/api/v1/seller/products/{ids['spu_main']}", token=tokens["seller"], json={"description": "updated before review"})
    req("seller sku update draft deprecated", "PATCH", f"/api/v1/seller/skus/{ids['sku_main']}", token=tokens["seller"], expected=(410,), json={"price": "8.60", "stock_available": 120})
    req("seller submit main", "POST", f"/api/v1/seller/products/{ids['spu_main']}/submit", token=tokens["seller"])
    req("seller submit rejected product", "POST", f"/api/v1/seller/products/{ids['spu_rejected']}/submit", token=tokens["seller"])
    req("seller submit offlinecycle", "POST", f"/api/v1/seller/products/{ids['spu_offline']}/submit", token=tokens["seller"])
    req("admin pending products", "GET", "/api/v1/admin/products/pending", token=tokens["admin"])
    req("admin reject product", "POST", f"/api/v1/admin/products/{ids['spu_rejected']}/reject", token=tokens["admin"], json={"reason": "reject visibility test"})
    req("admin approve main", "POST", f"/api/v1/admin/products/{ids['spu_main']}/approve", token=tokens["admin"], json={"reason": "approve main"})
    req("admin approve offlinecycle", "POST", f"/api/v1/admin/products/{ids['spu_offline']}/approve", token=tokens["admin"], json={"reason": "approve offline cycle"})
    req("public product rejected hidden detail", "GET", f"/api/v1/products/{ids['spu_rejected']}", expected=(404,))
    req("public products list db", "GET", f"/api/v1/products?q={quote(prefix)}&page=1&page_size=20")
    req("public product detail main", "GET", f"/api/v1/products/{ids['spu_main']}")
    req("seller offline product", "POST", f"/api/v1/seller/products/{ids['spu_offline']}/offline", token=tokens["seller"])
    online_again = must("seller online requires review", "POST", f"/api/v1/seller/products/{ids['spu_offline']}/online", token=tokens["seller"])
    log("online action moved to pending_review", online_again.get("status") == "pending_review", online_again.get("status"))
    req("offlinecycle hidden while pending", "GET", f"/api/v1/products/{ids['spu_offline']}", expected=(404,))

    reindex_resp, reindex_body = req("admin search reindex", "POST", "/api/v1/admin/search/reindex", token=tokens["admin"], category="external")
    if reindex_resp.status_code == 200:
        tasks = wait_meili_tasks(reindex_body.get("task_uids") or [], timeout=120)
        failed_tasks = [task for task in tasks if task and task.get("status") != "succeeded"]
        log("meili reindex tasks succeeded", not failed_tasks, failed_tasks)
    search_resp, search_body = req(
        "home search meili",
        "GET",
        f"/api/v1/search?q={quote(prefix + ' Tomato')}&sort_by=relevance&page=1&page_size=10",
        category="external",
    )
    if search_resp.status_code == 200:
        names = [item["name"] for item in search_body["items"]]
        log("search includes online main product", any(prefix + " Tomato" in name for name in names), names)
        log("search excludes rejected product", not any("Rejected Product" in name for name in names), names)
    for sort_by in ("price_asc", "price_desc", "stock_desc", "newest"):
        filtered_resp, filtered_body = req(
            f"home search category filter sort {sort_by}",
            "GET",
            f"/api/v1/search?q={quote(prefix)}&category_id={ids['category_id']}&sort_by={sort_by}&page=1&page_size=10",
            category="external",
        )
        if filtered_resp.status_code == 200:
            log(
                f"home search category filter applies {sort_by}",
                all(item["category_id"] == ids["category_id"] for item in filtered_body["items"]),
                filtered_body["items"],
            )
    req(
        "home search origin filter",
        "GET",
        f"/api/v1/search?q={quote(prefix)}&origin_place={quote(prefix + ' Origin')}&page=1&page_size=10",
        category="external",
    )
    for sort_by in ("price_asc", "price_desc", "stock_desc", "newest"):
        req(
            f"public products db sort {sort_by}",
            "GET",
            f"/api/v1/products?q={quote(prefix)}&category_id={ids['category_id']}&sort_by={sort_by}&page=1&page_size=10",
        )

    req("buyer wallet get initial", "GET", "/api/v1/orders/wallet", token=tokens["buyer"])
    recharge_key = f"{prefix}-recharge-1"
    req("buyer wallet recharge", "POST", "/api/v1/orders/wallet/recharge", token=tokens["buyer"], json={"amount": "5000.00", "idempotency_key": recharge_key})
    before = db_wallet(ids["buyer_user_id"])
    req("buyer wallet recharge idempotent retry", "POST", "/api/v1/orders/wallet/recharge", token=tokens["buyer"], json={"amount": "5000.00", "idempotency_key": recharge_key})
    after = db_wallet(ids["buyer_user_id"])
    log("wallet recharge idempotent balance stable", before == after, f"before={before} after={after}")
    req("negative recharge rejected", "POST", "/api/v1/orders/wallet/recharge", token=tokens["buyer"], expected=(422,), json={"amount": "-1.00", "idempotency_key": f"{prefix}-bad-recharge"})

    temp_cart = must(
        "cart add then delete",
        "POST",
        "/api/v1/cart/items",
        token=tokens["buyer"],
        expected=(201,),
        json={"sku_id": ids["sku_main"], "quantity": 1, "selected": False},
    )
    temp_id = [item["id"] for item in temp_cart["items"] if item["sku_id"] == ids["sku_main"]][-1]
    req("cart patch item", "PATCH", f"/api/v1/cart/items/{temp_id}", token=tokens["buyer"], json={"quantity": 2, "selected": True})
    req("cart delete item", "DELETE", f"/api/v1/cart/items/{temp_id}", token=tokens["buyer"])
    req("cart get", "GET", "/api/v1/cart", token=tokens["buyer"])

    unpaid = add_cart_and_order(tokens["buyer"], ids["sku_main"], "unpaid-cancel")
    req("seller cannot see unpaid order", "GET", f"/api/v1/seller/orders/{unpaid['id']}", token=tokens["seller"], expected=(404,))
    req("cancel wait_pay order", "POST", f"/api/v1/orders/{unpaid['id']}/cancel", token=tokens["buyer"])
    log("wait_pay cancel status", db_order(unpaid["id"])[0] == "CANCELLED", db_order(unpaid["id"]))

    paid_cancel = add_cart_and_order(tokens["buyer"], ids["sku_main"], "paid-cancel")
    req("pay paid-cancel order", "POST", f"/api/v1/orders/{paid_cancel['id']}/pay", token=tokens["buyer"])
    req("seller sees paid order", "GET", f"/api/v1/seller/orders/{paid_cancel['id']}", token=tokens["seller"])
    req("cancel paid unshipped order", "POST", f"/api/v1/orders/{paid_cancel['id']}/cancel", token=tokens["buyer"])
    log("paid unshipped cancel status", db_order(paid_cancel["id"])[0] == "CANCELLED", db_order(paid_cancel["id"]))

    timeout_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "timeout")
    with Session.begin() as db:
        order = db.get(Order, timeout_order["id"])
        order.payment_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    req("expired wait_pay pay returns expired detail", "POST", f"/api/v1/orders/{timeout_order['id']}/pay", token=tokens["buyer"])
    req("expired wait_pay detail triggers expiration", "GET", f"/api/v1/orders/{timeout_order['id']}", token=tokens["buyer"])
    log("timeout order expired", db_order(timeout_order["id"])[0] == "EXPIRED", db_order(timeout_order["id"]))

    completed_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "complete")
    pay_order(tokens["buyer"], completed_order["id"], "pay complete order")
    ship_order(tokens["seller"], completed_order["id"], "ship complete order")
    req("cancel shipped forbidden", "POST", f"/api/v1/orders/{completed_order['id']}/cancel", token=tokens["buyer"], expected=(400,))
    complete_body = must("buyer complete order", "POST", f"/api/v1/orders/{completed_order['id']}/complete", token=tokens["buyer"])
    ids["completed_order"] = completed_order["id"]
    ids["completed_order_item"] = complete_body["items"][0]["id"]
    log("completed order status", db_order(completed_order["id"])[0] == "COMPLETED", db_order(completed_order["id"]))
    req("buyer orders list", "GET", "/api/v1/orders", token=tokens["buyer"])
    req("buyer order detail", "GET", f"/api/v1/orders/{completed_order['id']}", token=tokens["buyer"])
    req("seller orders list status filter", "GET", "/api/v1/seller/orders?status_filter=COMPLETED", token=tokens["seller"])
    req("seller dashboard", "GET", "/api/v1/seller/dashboard", token=tokens["seller"])
    req("seller wallet", "GET", "/api/v1/seller/wallet", token=tokens["seller"])
    req("seller earnings", "GET", "/api/v1/seller/earnings", token=tokens["seller"])

    review = must(
        "buyer review completed order",
        "POST",
        "/api/v1/orders/reviews",
        token=tokens["buyer"],
        expected=(201,),
        json={"order_item_id": ids["completed_order_item"], "rating": 5, "content": "fresh final product", "images_json": []},
    )
    ids["review_id"] = review["id"]
    req(
        "duplicate review rejected",
        "POST",
        "/api/v1/orders/reviews",
        token=tokens["buyer"],
        expected=(409,),
        json={"order_item_id": ids["completed_order_item"], "rating": 4, "content": "duplicate", "images_json": []},
    )
    req("buyer reviews list", "GET", "/api/v1/orders/reviews", token=tokens["buyer"])
    req("seller reviews list", "GET", "/api/v1/seller/reviews", token=tokens["seller"])
    req("seller reply review", "POST", f"/api/v1/seller/reviews/{ids['review_id']}/reply", token=tokens["seller"], json={"seller_reply": "thanks"})

    refund_pre_ship_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "refund-before-ship")
    pay_order(tokens["buyer"], refund_pre_ship_order["id"], "pay refund-before-ship")
    req("refund before shipment rejected", "POST", "/api/v1/refunds", token=tokens["buyer"], expected=(400,), json={"order_id": refund_pre_ship_order["id"], "reason": "not shipped"})

    shipped_refund_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "seller-approve-shipped")
    pay_order(tokens["buyer"], shipped_refund_order["id"], "pay seller-approve-shipped")
    ship_order(tokens["seller"], shipped_refund_order["id"], "ship seller-approve-shipped")
    refund1 = must("buyer refund shipped", "POST", "/api/v1/refunds", token=tokens["buyer"], expected=(201,), json={"order_id": shipped_refund_order["id"], "reason": "refund shipped"})
    req("buyer dispute pending not overdue rejected", "POST", "/api/v1/refunds/disputes", token=tokens["buyer"], expected=(400,), json={"refund_id": refund1["id"], "reason": "too early"})
    req("buyer refunds list", "GET", "/api/v1/refunds", token=tokens["buyer"])
    req("seller refunds list", "GET", "/api/v1/seller/refunds", token=tokens["seller"])
    req("seller approve shipped refund", "POST", f"/api/v1/seller/refunds/{refund1['id']}/approve", token=tokens["seller"], json={"seller_note": "approved shipped"})
    log("shipped refund final order refunded", db_order(shipped_refund_order["id"])[0] == "REFUNDED", db_order(shipped_refund_order["id"]))

    completed_refund_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "seller-approve-completed")
    pay_order(tokens["buyer"], completed_refund_order["id"], "pay seller-approve-completed")
    ship_order(tokens["seller"], completed_refund_order["id"], "ship seller-approve-completed")
    req("complete seller-approve-completed", "POST", f"/api/v1/orders/{completed_refund_order['id']}/complete", token=tokens["buyer"])
    refund2 = must("buyer refund completed", "POST", "/api/v1/refunds", token=tokens["buyer"], expected=(201,), json={"order_id": completed_refund_order["id"], "reason": "refund completed"})
    req("seller approve completed refund", "POST", f"/api/v1/seller/refunds/{refund2['id']}/approve", token=tokens["seller"], json={"seller_note": "approved completed"})
    log("completed refund final order refunded", db_order(completed_refund_order["id"])[0] == "REFUNDED", db_order(completed_refund_order["id"]))

    admin_reject_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "admin-reject-refund")
    pay_order(tokens["buyer"], admin_reject_order["id"], "pay admin-reject-refund")
    ship_order(tokens["seller"], admin_reject_order["id"], "ship admin-reject-refund")
    refund_admin_reject = must("buyer refund admin reject path", "POST", "/api/v1/refunds", token=tokens["buyer"], expected=(201,), json={"order_id": admin_reject_order["id"], "reason": "admin reject path"})
    req("admin refunds list", "GET", "/api/v1/admin/refunds", token=tokens["admin"])
    req("admin reject refund", "POST", f"/api/v1/admin/refunds/{refund_admin_reject['id']}/reject", token=tokens["admin"], json={"admin_note": "admin rejects redundant path"})
    log("admin rejected refund keeps shipped", db_order(admin_reject_order["id"])[0] == "SHIPPED", db_order(admin_reject_order["id"]))

    admin_approve_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "admin-approve-refund")
    pay_order(tokens["buyer"], admin_approve_order["id"], "pay admin-approve-refund")
    ship_order(tokens["seller"], admin_approve_order["id"], "ship admin-approve-refund")
    refund_admin_approve = must("buyer refund admin approve path", "POST", "/api/v1/refunds", token=tokens["buyer"], expected=(201,), json={"order_id": admin_approve_order["id"], "reason": "admin approve path"})
    req("admin approve refund", "POST", f"/api/v1/admin/refunds/{refund_admin_approve['id']}/approve", token=tokens["admin"], json={"admin_note": "admin approves redundant path"})
    log("admin approved refund order refunded", db_order(admin_approve_order["id"])[0] == "REFUNDED", db_order(admin_approve_order["id"]))

    dispute_approve_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "dispute-approve")
    pay_order(tokens["buyer"], dispute_approve_order["id"], "pay dispute-approve")
    ship_order(tokens["seller"], dispute_approve_order["id"], "ship dispute-approve")
    refund3 = must("buyer refund dispute approve", "POST", "/api/v1/refunds", token=tokens["buyer"], expected=(201,), json={"order_id": dispute_approve_order["id"], "reason": "seller reject then dispute"})
    req("seller reject refund", "POST", f"/api/v1/seller/refunds/{refund3['id']}/reject", token=tokens["seller"], json={"seller_note": "reject for dispute"})
    dispute = must("buyer create dispute after reject", "POST", "/api/v1/refunds/disputes", token=tokens["buyer"], expected=(201,), json={"refund_id": refund3["id"], "reason": "dispute rejected refund", "description": "admin please review", "evidence_images_json": []})
    req("refund disputes buyer list", "GET", "/api/v1/refunds/disputes", token=tokens["buyer"])
    req("admin disputes list", "GET", "/api/v1/admin/disputes", token=tokens["admin"])
    req("admin approve dispute", "POST", f"/api/v1/admin/disputes/{dispute['id']}/approve", token=tokens["admin"], json={"resolution_note": "approve buyer dispute"})
    log("dispute approve order refunded", db_order(dispute_approve_order["id"])[0] == "REFUNDED", db_order(dispute_approve_order["id"]))

    dispute_reject_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "dispute-reject")
    pay_order(tokens["buyer"], dispute_reject_order["id"], "pay dispute-reject")
    ship_order(tokens["seller"], dispute_reject_order["id"], "ship dispute-reject")
    refund4 = must("buyer refund dispute reject", "POST", "/api/v1/refunds", token=tokens["buyer"], expected=(201,), json={"order_id": dispute_reject_order["id"], "reason": "seller reject then admin reject dispute"})
    req("seller reject refund for admin reject dispute", "POST", f"/api/v1/seller/refunds/{refund4['id']}/reject", token=tokens["seller"], json={"seller_note": "reject for admin reject dispute"})
    dispute2 = must("buyer create dispute admin reject", "POST", "/api/v1/refunds/disputes", token=tokens["buyer"], expected=(201,), json={"refund_id": refund4["id"], "reason": "dispute to reject"})
    req("admin reject dispute", "POST", f"/api/v1/admin/disputes/{dispute2['id']}/reject", token=tokens["admin"], json={"resolution_note": "reject buyer dispute"})
    log("dispute reject keeps shipped", db_order(dispute_reject_order["id"])[0] == "SHIPPED", db_order(dispute_reject_order["id"]))

    timeout_refund_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "refund-timeout")
    pay_order(tokens["buyer"], timeout_refund_order["id"], "pay refund-timeout")
    ship_order(tokens["seller"], timeout_refund_order["id"], "ship refund-timeout")
    refund_timeout = must("buyer refund timeout path", "POST", "/api/v1/refunds", token=tokens["buyer"], expected=(201,), json={"order_id": timeout_refund_order["id"], "reason": "timeout path"})
    with Session.begin() as db:
        refund = db.get(RefundApplication, refund_timeout["id"])
        refund.seller_deadline_at = datetime.now(UTC) - timedelta(days=1)
    timeout_dispute = must("buyer dispute overdue pending creates dispute", "POST", "/api/v1/refunds/disputes", token=tokens["buyer"], expected=(201,), json={"refund_id": refund_timeout["id"], "reason": "seller timeout"})
    log("timeout dispute created", bool(timeout_dispute.get("id")), timeout_dispute)

    req("buyer2 cannot see buyer order", "GET", f"/api/v1/orders/{ids['completed_order']}", token=tokens["buyer2"], expected=(404,))
    req("buyer2 cannot dispute buyer refund", "POST", "/api/v1/refunds/disputes", token=tokens["buyer2"], expected=(404,), json={"refund_id": refund3["id"], "reason": "not mine"})
    req("seller cannot approve nonexistent refund", "POST", "/api/v1/seller/refunds/999999999/approve", token=tokens["seller"], expected=(404,), json={"seller_note": "bad"})
    req("admin users list", "GET", "/api/v1/admin/users", token=tokens["admin"])
    req("admin disable buyer2", "POST", f"/api/v1/admin/users/{ids['buyer2_user_id']}/disable", token=tokens["admin"])
    req("disabled buyer2 login rejected", "POST", "/api/v1/auth/buyer/login", expected=(403,), json={"identifier": buyer2_username, "password": password})
    req("admin enable buyer2", "POST", f"/api/v1/admin/users/{ids['buyer2_user_id']}/enable", token=tokens["admin"])
    req("enabled buyer2 login ok", "POST", "/api/v1/auth/buyer/login", json={"identifier": buyer2_username, "password": password})
    req("admin disable seller hides public db", "POST", f"/api/v1/admin/users/{ids['seller_user_id']}/disable", token=tokens["admin"])
    req("disabled seller token rejected", "GET", "/api/v1/seller/dashboard", token=tokens["seller"], expected=(403,))
    req("disabled seller product hidden db detail", "GET", f"/api/v1/products/{ids['spu_main']}", expected=(404,))
    req("admin enable seller", "POST", f"/api/v1/admin/users/{ids['seller_user_id']}/enable", token=tokens["admin"])
    tokens["seller"] = must("seller relogin after enable", "POST", "/api/v1/auth/seller/login", json={"identifier": seller_username, "password": password})["access_token"]

    recharge_concurrent_key = f"{prefix}-recharge-concurrent"

    def recharge_once(_: int) -> int:
        return client.post(
            "/api/v1/orders/wallet/recharge",
            headers=auth(tokens["buyer"]),
            json={"amount": "7.00", "idempotency_key": recharge_concurrent_key},
        ).status_code

    with ThreadPoolExecutor(max_workers=10) as executor:
        recharge_statuses = list(executor.map(recharge_once, range(10)))
    log("concurrent recharge same key no server error", all(code in {200, 409} for code in recharge_statuses), recharge_statuses)
    from app.services.commerce.service import _wallet_recharge_reference_id

    recharge_reference_id = _wallet_recharge_reference_id(recharge_concurrent_key)
    log(
        "concurrent recharge same key one ledger",
        ledger_count(ids["buyer_user_id"], WalletBizType.RECHARGE, "wallet_recharge", recharge_reference_id) == 1,
        ledger_count(ids["buyer_user_id"], WalletBizType.RECHARGE, "wallet_recharge", recharge_reference_id),
    )

    duplicate_order_cart = must(
        "cart add duplicate order key",
        "POST",
        "/api/v1/cart/items",
        token=tokens["buyer"],
        expected=(201,),
        json={"sku_id": ids["sku_main"], "quantity": 1, "selected": True},
    )
    duplicate_order_item_id = [item["id"] for item in duplicate_order_cart["items"] if item["sku_id"] == ids["sku_main"]][-1]
    duplicate_order_key = f"{prefix}-order-duplicate-concurrent"

    def create_same_order(_: int) -> int:
        return client.post(
            "/api/v1/orders",
            headers=auth(tokens["buyer"]),
            json={
                "idempotency_key": duplicate_order_key,
                "auto_pay": False,
                "cart_item_ids": [duplicate_order_item_id],
                "receiver_snapshot": make_receiver("duplicate-concurrent"),
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=10) as executor:
        duplicate_order_statuses = list(executor.map(create_same_order, range(10)))
    with Session() as db:
        duplicate_order_count = db.execute(
            select(func.count(Order.id)).where(
                Order.buyer_id == ids["buyer_user_id"],
                Order.checkout_idempotency_key == duplicate_order_key,
            )
        ).scalar_one()
        duplicate_order_qty = db.execute(
            select(func.coalesce(func.sum(OrderItem.quantity), 0))
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.buyer_id == ids["buyer_user_id"],
                Order.checkout_idempotency_key == duplicate_order_key,
                OrderItem.sku_id == ids["sku_main"],
            )
        ).scalar_one()
    log(
        "concurrent order idempotency same key no server error",
        all(code == 201 for code in duplicate_order_statuses),
        duplicate_order_statuses,
    )
    log(
        "concurrent order idempotency creates one order",
        duplicate_order_count == 1 and duplicate_order_qty == 1,
        f"orders={duplicate_order_count}, qty={duplicate_order_qty}",
    )

    pay_concurrent_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "pay-concurrent")

    def pay_once(_: int) -> int:
        return client.post(
            f"/api/v1/orders/{pay_concurrent_order['id']}/pay",
            headers=auth(tokens["buyer"]),
        ).status_code

    with ThreadPoolExecutor(max_workers=10) as executor:
        pay_statuses = list(executor.map(pay_once, range(10)))
    log("concurrent pay no server error", all(code in {200, 400} for code in pay_statuses), pay_statuses)
    log(
        "order pay ledger once",
        ledger_count(ids["buyer_user_id"], WalletBizType.ORDER_PAY, "order_pay", pay_concurrent_order["id"]) == 1,
        ledger_count(ids["buyer_user_id"], WalletBizType.ORDER_PAY, "order_pay", pay_concurrent_order["id"]),
    )

    pay_cancel_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "pay-cancel-race")

    def pay_or_cancel(index: int) -> tuple[str, int]:
        if index % 2 == 0:
            response = client.post(f"/api/v1/orders/{pay_cancel_order['id']}/pay", headers=auth(tokens["buyer"]))
            return ("pay", response.status_code)
        response = client.post(f"/api/v1/orders/{pay_cancel_order['id']}/cancel", headers=auth(tokens["buyer"]))
        return ("cancel", response.status_code)

    with ThreadPoolExecutor(max_workers=10) as executor:
        pay_cancel_results = list(executor.map(pay_or_cancel, range(10)))
    pay_cancel_state = db_order(pay_cancel_order["id"])
    log(
        "concurrent pay/cancel valid terminal state",
        pay_cancel_state[0] in {"PAID", "CANCELLED"},
        f"state={pay_cancel_state}, results={pay_cancel_results}",
    )

    ship_cancel_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "ship-cancel-race")
    pay_order(tokens["buyer"], ship_cancel_order["id"], "pay ship-cancel-race")

    def ship_or_cancel(index: int) -> tuple[str, int]:
        if index % 2 == 0:
            response = client.post(f"/api/v1/seller/orders/{ship_cancel_order['id']}/ship", headers=auth(tokens["seller"]))
            return ("ship", response.status_code)
        response = client.post(f"/api/v1/orders/{ship_cancel_order['id']}/cancel", headers=auth(tokens["buyer"]))
        return ("cancel", response.status_code)

    with ThreadPoolExecutor(max_workers=10) as executor:
        ship_cancel_results = list(executor.map(ship_or_cancel, range(10)))
    ship_cancel_state = db_order(ship_cancel_order["id"])
    log(
        "concurrent ship/cancel valid terminal state",
        ship_cancel_state[0] in {"SHIPPED", "CANCELLED"},
        f"state={ship_cancel_state}, results={ship_cancel_results}",
    )

    decision_race_order = add_cart_and_order(tokens["buyer"], ids["sku_main"], "refund-decision-race")
    pay_order(tokens["buyer"], decision_race_order["id"], "pay refund-decision-race")
    ship_order(tokens["seller"], decision_race_order["id"], "ship refund-decision-race")
    decision_race_refund = must(
        "buyer refund decision race path",
        "POST",
        "/api/v1/refunds",
        token=tokens["buyer"],
        expected=(201,),
        json={"order_id": decision_race_order["id"], "reason": "decision race"},
    )

    def approve_or_reject_refund(index: int) -> tuple[str, int]:
        action = "approve" if index % 2 == 0 else "reject"
        response = client.post(
            f"/api/v1/seller/refunds/{decision_race_refund['id']}/{action}",
            headers=auth(tokens["seller"]),
            json={"seller_note": f"race {action}"},
        )
        return (action, response.status_code)

    with ThreadPoolExecutor(max_workers=10) as executor:
        refund_decision_results = list(executor.map(approve_or_reject_refund, range(10)))
    refund_decision_state = db_order(decision_race_order["id"])
    with Session() as db:
        refund_state = db.get(RefundApplication, decision_race_refund["id"]).status.value
    log(
        "concurrent seller refund decision single final state",
        refund_state in {"completed", "rejected"} and refund_decision_state[0] in {"REFUNDED", "SHIPPED"},
        f"order={refund_decision_state}, refund={refund_state}, results={refund_decision_results}",
    )

    scarce = must("seller product create scarce", "POST", "/api/v1/seller/products", token=tokens["seller"], expected=(201,), json=product_payload(f"{prefix} Scarce", 3, price="1.00"))
    ids["spu_scarce"] = scarce["id"]
    ids["sku_scarce"] = scarce["skus"][0]["id"]
    req("seller submit scarce", "POST", f"/api/v1/seller/products/{ids['spu_scarce']}/submit", token=tokens["seller"])
    req("admin approve scarce", "POST", f"/api/v1/admin/products/{ids['spu_scarce']}/approve", token=tokens["admin"], json={"reason": "scarce concurrency"})

    worker_tokens = []
    for index in range(6):
        username = f"{prefix}C{index}"
        must(
            f"conc buyer {index} register",
            "POST",
            "/api/v1/auth/buyer/register",
            expected=(201,),
            json={"username": username, "password": password, "register_method": "email", "email": f"{username.lower()}@example.com"},
        )
        token = must(
            f"conc buyer {index} login",
            "POST",
            "/api/v1/auth/buyer/login",
            json={"identifier": username, "password": password},
        )["access_token"]
        req(f"conc buyer {index} recharge", "POST", "/api/v1/orders/wallet/recharge", token=token, json={"amount": "20.00", "idempotency_key": f"{prefix}-conc-recharge-{index}"})
        worker_tokens.append(token)

    def buy_scarce(item: tuple[int, str]):
        index, token = item
        try:
            cart = client.post("/api/v1/cart/items", headers=auth(token), json={"sku_id": ids["sku_scarce"], "quantity": 1, "selected": True})
            if cart.status_code != 201:
                return ("cart", cart.status_code)
            item_id = [entry["id"] for entry in cart.json()["items"] if entry["sku_id"] == ids["sku_scarce"]][-1]
            order = client.post(
                "/api/v1/orders",
                headers=auth(token),
                json={
                    "idempotency_key": f"{prefix}-scarce-{index}",
                    "auto_pay": True,
                    "cart_item_ids": [item_id],
                    "receiver_snapshot": make_receiver(f"scarce-{index}"),
                },
            )
            return ("order", order.status_code)
        except Exception as exc:
            return ("exc", str(exc)[:80])

    with ThreadPoolExecutor(max_workers=6) as executor:
        scarce_results = list(executor.map(buy_scarce, enumerate(worker_tokens)))
    stock_available, stock_locked, _ = db_sku(ids["sku_scarce"])
    with Session() as db:
        scarce_paid_qty = db.execute(
            select(func.coalesce(func.sum(OrderItem.quantity), 0))
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.idempotency_key.like(f"{prefix}-scarce-%"),
                Order.status.in_([OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.COMPLETED]),
                OrderItem.sku_id == ids["sku_scarce"],
            )
        ).scalar_one()
    log(
        "concurrent scarce stock never negative",
        stock_available >= 0 and stock_locked >= 0,
        f"results={scarce_results}, stock={stock_available}, locked={stock_locked}, paid_qty={scarce_paid_qty}",
    )
    log(
        "concurrent scarce no oversell and accounting matches",
        scarce_paid_qty <= 3 and stock_available == 3 - scarce_paid_qty and stock_locked == scarce_paid_qty,
        f"results={scarce_results}, stock={stock_available}, locked={stock_locked}, paid_qty={scarce_paid_qty}",
    )

    ai_resp, ai_body = req(
        "ai chat",
        "POST",
        "/api/v1/ai/chat",
        token=tokens["buyer"],
        category="external",
        json={"message": f"我想做{prefix} Tomato 炒鸡蛋，帮我准备食材", "candidate_limit": 5},
    )
    req("ai sessions list", "GET", "/api/v1/ai/sessions", token=tokens["buyer"])
    if ai_resp.status_code == 200 and ai_body.get("session_id"):
        req("ai session detail", "GET", f"/api/v1/ai/sessions/{ai_body['session_id']}", token=tokens["buyer"])
    else:
        req("ai session detail missing route", "GET", "/api/v1/ai/sessions/999999999", token=tokens["buyer"], expected=(404,))

    req("admin dashboard", "GET", "/api/v1/admin/dashboard", token=tokens["admin"])
    req("admin search reindex final", "POST", "/api/v1/admin/search/reindex", token=tokens["admin"], category="external")


try:
    run()
except Exception as exc:
    log("SCRIPT_ABORT", False, repr(exc))

print("\n=== FINAL_TEST_SUMMARY ===")
print("prefix", prefix)
print("ids", json.dumps(ids, ensure_ascii=False, default=str))
passes = sum(1 for item in results if item["ok"] and item["category"] != "external")
externals = sum(1 for item in results if item["ok"] and item["category"] == "external")
failures = [item for item in results if not item["ok"]]
print("pass_count", passes)
print("external_count", externals)
print("fail_count", len(failures))
for item in failures:
    print("FAIL_ITEM", json.dumps(item, ensure_ascii=False, default=str))
for item in external_notes:
    print("EXTERNAL_NOTE", json.dumps(item, ensure_ascii=False, default=str)[:1000])
