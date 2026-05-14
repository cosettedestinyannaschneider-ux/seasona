from sqlalchemy import BigInteger, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AiMessageRole
from app.models.mixins import TimestampMixin
from app.models.sqltypes import enum_column


class AiChatSession(TimestampMixin, Base):
    __tablename__ = "ai_chat_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    buyer_id: Mapped[int | None] = mapped_column(ForeignKey("user_account.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(128))
    state_json: Mapped[dict | None] = mapped_column(JSON)


class AiChatMessage(TimestampMixin, Base):
    __tablename__ = "ai_chat_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("ai_chat_session.id"), index=True)
    role: Mapped[AiMessageRole] = mapped_column(enum_column(AiMessageRole), index=True)
    content: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
