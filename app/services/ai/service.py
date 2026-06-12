from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status
import httpx
from openai import APITimeoutError
from sqlalchemy import select

from app.core.config import get_settings
from app.models.ai import AiChatMessage, AiChatSession
from app.models.enums import AiMessageRole, UserRole
from app.schemas.ai import (
    AiChatResponse,
    AiChatStatus,
    AiIngredientMatch,
    AiMessagePublic,
    AiSessionDetail,
    AiSessionPublic,
)
from app.services.ai.clients import get_llm_client
from app.services.search.service import search_products_for_ai_ingredient


AI_INTENT_PROMPT = """
    # 角色设定
你是一个为生鲜电商平台服务的“智能采购助手”。你的唯一职责是：通过对话了解用户想做什么菜，并逆向分析出该菜品所需的【主要食材】，最终为用户生成采购清单。

# 核心能力与约束
1. **边界严格控制（拒绝非食品话题）：**
   - 你的服务范围仅限“菜品”与“食材”。
   - 如果用户询问厨具（如锅、铲子、烤箱）、天气、闲聊或其他任何非食品话题，你必须委婉拒绝，并引导回食品采购上。例如：“抱歉，我是生鲜采购助手，仅能提供食材采购建议。请问您今天打算做点什么菜？”
2. **禁止提供烹饪指导：**
   - 本平台不提供菜谱和做法。如果用户问“xxx怎么做”，你必须拒绝提供步骤，但要询问是否需要购买该菜品的食材。例如：“我无法为您提供具体的烹饪步骤，但如果您想做【红烧肉】，我可以为您查找需要的五花肉等食材。需要我现在列出清单吗？”
3. **消除歧义（多轮询问）：**
   - 当用户提出的需求过于笼统（如“我想做蛋糕”、“我想吃点辣的”）时，不要急于给出食材。请主动询问更具体的菜名或口味偏好，直到用户给出明确具体菜品或可以直接查找的食材（例如用户直接说我想买鸡蛋，也可以直接执行搜索）。
4. **俗名与别名识别：**
   - 你需要利用自身知识库准确识别具有特殊名称的菜品。例如：“蚂蚁上树”对应猪肉末和粉丝；“老婆饼”对应面粉、冬瓜糖、芝麻等；“鱼香肉丝”对应猪肉、木耳、笋丝等。
5. **食材提取标准：**
   - 仅提取【主要食材】。
   - 默认用户家中已有常用调味料（油、盐、酱、醋、糖等），不要将其作为主食材返回。但可以将葱、姜、蒜等辅料作为“可选补充”记下，预备用户的进一步要求。

# 严格输出格式
你必须且只能以 JSON 格式输出回复。任何情况下都绝对禁止在 JSON 结构之外输出任何多余的文字。如遇无法处理的未知错误，请返回 `{}`。

你的 JSON 必须遵循以下结构：
{
  "status": "chat", // 状态枚举值："chat"(需要进一步沟通)、"reject"(拒绝请求)、"success"(成功锁定菜品并填充食材列表)
  "reply": "", //  仅当 status 为 "chat" 或 "reject" 时填写回复的话，这里写你需要对用户说的自然语言回复（如提问、拒绝的引导语，确认语或追问）。但当 status 为 "success" 时，此处必须留空 ""！
  "items": [], // 仅在 status 为 "success" 时，包含提取出的主要食材数组。其他状态为空数组。
}

# 示例参考（Few-Shot）

用户输入：“你们这锅怎么卖？”
你的输出：
{
  "status": "reject",
  "reply": "抱歉，我是生鲜采购助手，不提供厨具售卖。请问您今晚打算做点什么菜，需要我帮您采购食材吗？",
  "items": []
}

用户输入：“我想吃点甜点”
你的输出：
{
  "status": "chat",
  "reply": "好的！甜点有很多种呢，比如草莓蛋糕、蛋挞或者是中式的老婆饼。您具体想做哪一种呢？",
  "items": []
}

用户输入：“蚂蚁上树怎么做啊”
你的输出：
{
  "status": "chat",
  "reply": "我无法为您提供具体的烹饪指导，但蚂蚁上树是一道经典的川菜，如果您准备做这道菜，我可以为您列出购买所需主要食材的清单",
  "items": []
}

用户输入：“对，帮我准备蚂蚁上树的食材吧”
你的输出：
{
  "status": "success",
  "reply": "",
  "items": ["猪肉", "红薯粉丝"]
}

用户输入：“我想做西红柿炒鸡蛋”
你的输出：
{
  "status": "success",
  "reply": "",
  "items": ["西红柿", "鸡蛋"]
}
    """.strip()


def _role_value(user: Any) -> str:
    return getattr(user.role, "value", user.role)


def _ensure_buyer(user: Any) -> None:
    if _role_value(user) != UserRole.BUYER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Buyer permission required.",
        )


def _create_session(db: Any, buyer: Any, message: str) -> AiChatSession:
    session = AiChatSession(
        buyer_id=buyer.id,
        title=message[:40],
        state_json={},
    )
    db.add(session)
    db.flush()
    return session


def _get_session_for_buyer(db: Any, buyer: Any, session_id: int | None, message: str) -> AiChatSession:
    if session_id is None:
        return _create_session(db, buyer, message)
    session = db.execute(
        select(AiChatSession)
        .where(AiChatSession.id == session_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if session is None or session.buyer_id != buyer.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI chat session not found.",
        )
    return session


def _session_is_locked(session: AiChatSession) -> bool:
    state = session.state_json or {}
    return bool(state.get("locked"))


def _message_to_public(message: AiChatMessage) -> AiMessagePublic:
    return AiMessagePublic(
        id=message.id,
        session_id=message.session_id,
        role=getattr(message.role, "value", message.role),
        content=message.content,
        payload_json=message.payload_json,
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


def list_sessions(db: Any, buyer: Any, *, page: int = 1, page_size: int = 20) -> list[AiSessionPublic]:
    _ensure_buyer(buyer)
    sessions = db.execute(
        select(AiChatSession)
        .where(AiChatSession.buyer_id == buyer.id)
        .order_by(AiChatSession.updated_at.desc(), AiChatSession.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return [
        AiSessionPublic(
            id=item.id,
            buyer_id=item.buyer_id,
            title=item.title,
            state_json=item.state_json,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in sessions
    ]


def get_session_detail(db: Any, buyer: Any, session_id: int) -> AiSessionDetail:
    _ensure_buyer(buyer)
    session = db.get(AiChatSession, session_id)
    if session is None or session.buyer_id != buyer.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI chat session not found.",
        )
    messages = db.execute(
        select(AiChatMessage)
        .where(AiChatMessage.session_id == session.id)
        .order_by(AiChatMessage.id.asc())
    ).scalars().all()
    return AiSessionDetail(
        id=session.id,
        buyer_id=session.buyer_id,
        title=session.title,
        state_json=session.state_json,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[_message_to_public(message) for message in messages],
    )


def _recent_messages_for_llm(db: Any, session_id: int, limit: int = 8) -> list[dict[str, str]]:
    rows = db.execute(
        select(AiChatMessage)
        .where(AiChatMessage.session_id == session_id)
        .order_by(AiChatMessage.id.desc())
        .limit(limit)
    ).scalars().all()
    messages: list[dict[str, str]] = [{"role": "system", "content": AI_INTENT_PROMPT}]
    for item in reversed(rows):
        role = getattr(item.role, "value", item.role)
        if role not in {"user", "assistant"}:
            continue
        messages.append({"role": role, "content": item.content})
    return messages


def _parse_llm_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM returned invalid JSON.",
        ) from exc

    status_value = payload.get("status")
    if status_value not in {item.value for item in AiChatStatus}:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM returned unsupported status.",
        )
    items = payload.get("items") or []
    if not isinstance(items, list):
        items = []
    normalized_items = []
    for item in items:
        text_item = str(item).strip()
        if text_item and text_item not in normalized_items:
            normalized_items.append(text_item)
        if len(normalized_items) >= 6:
            break
    return {
        "status": status_value,
        "reply": str(payload.get("reply") or ""),
        "items": normalized_items,
    }


def extract_ingredients(db: Any, session: AiChatSession, user_message: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SEASONA_LLM_MODEL is not configured.",
        )
    try:
        client = get_llm_client()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    messages = _recent_messages_for_llm(db, session.id)
    messages.append({"role": "user", "content": user_message})
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            response_format={"type": "json_object"},
        )
    except (APITimeoutError, httpx.TimeoutException) as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM provider request timed out.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM provider request failed.",
        ) from exc
    raw_content = response.choices[0].message.content or "{}"
    return _parse_llm_payload(raw_content)


def match_products_for_ingredient(
    db: Any,
    ingredient: str,
    *,
    limit: int = 5,
) -> AiIngredientMatch:
    ingredient = ingredient.strip()
    if not ingredient:
        return AiIngredientMatch(ingredient=ingredient, candidates=[], missing=True)

    cards = search_products_for_ai_ingredient(db, ingredient, limit=limit)
    return AiIngredientMatch(
        ingredient=ingredient,
        candidates=cards,
        missing=not cards,
    )


def chat_with_assistant(
    db: Any,
    buyer: Any,
    *,
    message: str,
    session_id: int | None,
    candidate_limit: int = 5,
) -> AiChatResponse:
    _ensure_buyer(buyer)
    session = _get_session_for_buyer(db, buyer, session_id, message)
    if _session_is_locked(session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AI chat session is locked after generating product candidates.",
        )
    db.add(
        AiChatMessage(
            session_id=session.id,
            role=AiMessageRole.USER,
            content=message,
            payload_json=None,
        )
    )
    db.flush()

    parsed = extract_ingredients(db, session, message)
    status_value = AiChatStatus(parsed["status"])
    if status_value == AiChatStatus.SUCCESS and not parsed["items"]:
        status_value = AiChatStatus.CHAT
        parsed["reply"] = parsed["reply"] or "我还没有整理出明确的主要食材，请再具体描述一下您想做的菜。"
    ingredients: list[str] = parsed["items"] if status_value == AiChatStatus.SUCCESS else []
    results = [
        match_products_for_ingredient(db, item, limit=candidate_limit)
        for item in ingredients
    ]
    missing_items = [item.ingredient for item in results if item.missing]
    has_matches = any(not item.missing for item in results)
    locked = status_value == AiChatStatus.SUCCESS
    assistant_payload = {
        "status": status_value.value,
        "reply": parsed["reply"],
        "items": ingredients,
        "results": [item.model_dump(mode="json") for item in results],
        "locked": locked,
        "missing_items": missing_items,
        "has_matches": has_matches,
    }
    if parsed["reply"]:
        assistant_content = parsed["reply"]
    elif ingredients:
        assistant_content = f"我整理出这些主要食材：{'、'.join(ingredients)}。候选商品已按食材分组放在下方。"
    else:
        assistant_content = "我还需要再确认一下您的食材需求。"
    db.add(
        AiChatMessage(
            session_id=session.id,
            role=AiMessageRole.ASSISTANT,
            content=assistant_content,
            payload_json=assistant_payload,
        )
    )
    session.state_json = {
        "last_status": status_value.value,
        "last_items": ingredients,
        "locked": locked,
        "missing_items": missing_items,
        "has_matches": has_matches,
    }
    db.flush()

    return AiChatResponse(
        session_id=session.id,
        status=status_value,
        reply=parsed["reply"],
        ingredients=ingredients,
        results=results,
        locked=locked,
        missing_items=missing_items,
        has_matches=has_matches,
    )
