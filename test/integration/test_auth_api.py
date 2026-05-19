from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.order import Cart
from app.models.user import MerchantProfile, UserAccount
from app.models.wallet import WalletAccount
from test.factories import BuyerRegisterRequestFactory, SellerRegisterRequestFactory


pytestmark = [pytest.mark.integration, pytest.mark.api]


def test_buyer_register_login_me_and_logout_flow(app_client, db_session) -> None:
    payload = BuyerRegisterRequestFactory.build(
        username="BuyerFlow1",
        phone="13800000001",
        nickname="Buyer Flow",
    ).model_dump(mode="json")

    register_response = app_client.post("/api/v1/auth/buyer/register", json=payload)

    assert register_response.status_code == 201
    body = register_response.json()
    token = body["access_token"]
    user_id = body["user"]["id"]
    assert body["user"]["role"] == "buyer"
    assert db_session.execute(select(WalletAccount).where(WalletAccount.user_id == user_id)).scalar_one()
    assert db_session.execute(select(Cart).where(Cart.buyer_id == user_id)).scalar_one()

    login_response = app_client.post(
        "/api/v1/auth/buyer/login",
        json={"identifier": "13800000001", "password": "password123"},
    )
    assert login_response.status_code == 200

    me_response = app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "BuyerFlow1"

    logout_response = app_client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_response.status_code == 200
    revoked_response = app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert revoked_response.status_code == 401


def test_seller_registration_creates_draft_merchant_profile(app_client, db_session) -> None:
    response = app_client.post(
        "/api/v1/auth/seller/register",
        json={
            **SellerRegisterRequestFactory.build(
                shop_name="Demo Farm",
                username="SellerFlow1",
                phone="13900000001",
                email="seller@example.com",
                shop_description="test shop",
            ).model_dump(mode="json"),
        },
    )

    assert response.status_code == 201
    user = db_session.execute(select(UserAccount).where(UserAccount.username == "SellerFlow1")).scalar_one()
    merchant = db_session.execute(select(MerchantProfile).where(MerchantProfile.user_id == user.id)).scalar_one()
    wallet = db_session.execute(select(WalletAccount).where(WalletAccount.user_id == user.id)).scalar_one()
    assert merchant.audit_status.value == "draft"
    assert merchant.contact_phone == "13900000001"
    assert wallet.available_balance == 0


def test_duplicate_buyer_identifier_is_rejected(app_client) -> None:
    payload = {
        "username": "BuyerDup1",
        "password": "password123",
        "register_method": "email",
        "email": "dup@example.com",
    }
    assert app_client.post("/api/v1/auth/buyer/register", json=payload).status_code == 201

    duplicate = app_client.post(
        "/api/v1/auth/buyer/register",
        json={**payload, "username": "BuyerDup2"},
    )

    assert duplicate.status_code == 409
