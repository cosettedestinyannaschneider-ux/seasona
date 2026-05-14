from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import LedgerDirection, WalletBizType, WalletStatus
from app.models.mixins import TimestampMixin
from app.models.sqltypes import enum_column


class WalletAccount(TimestampMixin, Base):
    __tablename__ = "wallet_account"
    __table_args__ = (
        CheckConstraint("available_balance >= 0", name="ck_wallet_available_nonnegative"),
        CheckConstraint("frozen_balance >= 0", name="ck_wallet_frozen_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id"),
        unique=True,
        index=True,
    )
    available_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
    )
    frozen_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
    )
    version: Mapped[int] = mapped_column(default=0)
    status: Mapped[WalletStatus] = mapped_column(
        enum_column(WalletStatus),
        default=WalletStatus.ACTIVE,
        index=True,
    )


class WalletLedger(TimestampMixin, Base):
    __tablename__ = "wallet_ledger"
    __table_args__ = (
        UniqueConstraint(
            "wallet_account_id",
            "biz_type",
            "reference_type",
            "reference_id",
            name="uq_wallet_ledger_business_reference",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    wallet_account_id: Mapped[int] = mapped_column(
        ForeignKey("wallet_account.id"),
        index=True,
    )
    biz_type: Mapped[WalletBizType] = mapped_column(enum_column(WalletBizType), index=True)
    direction: Mapped[LedgerDirection] = mapped_column(enum_column(LedgerDirection))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    before_available_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    after_available_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    before_frozen_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    after_frozen_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reference_type: Mapped[str] = mapped_column(String(64), index=True)
    reference_id: Mapped[int] = mapped_column(BigInteger, index=True)
