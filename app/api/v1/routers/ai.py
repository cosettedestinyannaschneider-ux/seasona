from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.ai import AiChatRequest, AiChatResponse, AiSessionDetail, AiSessionPublic


router = APIRouter()


@router.get("/sessions", response_model=list[AiSessionPublic])
def list_chat_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> list[AiSessionPublic]:
    from app.services.ai.service import list_sessions

    return list_sessions(db, current_buyer, page=page, page_size=page_size)


@router.get("/sessions/{session_id}", response_model=AiSessionDetail)
def get_chat_session(
    session_id: int,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> AiSessionDetail:
    from app.services.ai.service import get_session_detail

    return get_session_detail(db, current_buyer, session_id)


@router.post("/chat", response_model=AiChatResponse, status_code=status.HTTP_200_OK)
def chat(
    payload: AiChatRequest,
    current_buyer: Any = Depends(require_roles(UserRole.BUYER)),
    db: Any = Depends(get_db),
) -> AiChatResponse:
    from app.services.ai.service import chat_with_assistant

    try:
        response = chat_with_assistant(
            db,
            current_buyer,
            message=payload.message,
            session_id=payload.session_id,
            candidate_limit=payload.candidate_limit,
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise
