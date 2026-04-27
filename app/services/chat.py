from sqlalchemy.orm import Session

from app.models.csat import Chat
from app.models.user import User
from app.repositories.chats import add_chat, add_message, get_chat_for_user, list_chats_for_user
from app.services.llm import get_llm_service


def list_user_chats(*, session: Session, user: User) -> list[Chat]:
    """Return persisted chats for a user."""
    return list_chats_for_user(session, user_id=user.id)


def get_user_chat(*, session: Session, user: User, chat_id: int) -> Chat | None:
    """Return a single chat if the user owns it."""
    return get_chat_for_user(session, chat_id=chat_id, user_id=user.id)


def create_chat_with_llm_reply(*, session: Session, user: User, prompt: str) -> Chat:
    """Create a new chat and persist an LLM-generated assistant reply."""
    chat = create_chat_with_user_message(session=session, user=user, prompt=prompt)
    try:
        assistant_reply = get_llm_service().generate_reply(messages=chat.messages)
        return persist_assistant_reply(session=session, chat=chat, content=assistant_reply)
    except Exception:
        session.rollback()
        raise


def append_llm_reply(*, session: Session, chat: Chat, prompt: str) -> Chat:
    """Append a user message and an LLM-generated assistant message to an existing chat."""
    updated_chat = append_user_message(session=session, chat=chat, prompt=prompt)
    try:
        assistant_reply = get_llm_service().generate_reply(messages=updated_chat.messages)
        return persist_assistant_reply(session=session, chat=updated_chat, content=assistant_reply)
    except Exception:
        session.rollback()
        raise


def create_chat_with_user_message(*, session: Session, user: User, prompt: str) -> Chat:
    """Create a new chat and persist only the initial user message."""
    normalized_prompt = prompt.strip()
    chat = add_chat(
        session,
        user_id=user.id,
        title=_build_chat_title(normalized_prompt),
    )
    add_message(session, chat_id=chat.id, role='user', content=normalized_prompt)
    session.commit()
    session.expire_all()
    return get_chat_for_user(session, chat_id=chat.id, user_id=user.id) or chat


def append_user_message(*, session: Session, chat: Chat, prompt: str) -> Chat:
    """Persist a new user message in an existing chat."""
    normalized_prompt = prompt.strip()
    add_message(session, chat_id=chat.id, role='user', content=normalized_prompt)
    session.commit()
    session.expire_all()
    return get_chat_for_user(session, chat_id=chat.id, user_id=chat.user_id) or chat


def persist_assistant_reply(*, session: Session, chat: Chat, content: str) -> Chat:
    """Persist a generated assistant reply."""
    add_message(session, chat_id=chat.id, role='assistant', content=content)
    session.commit()
    session.expire_all()
    return get_chat_for_user(session, chat_id=chat.id, user_id=chat.user_id) or chat


def _build_chat_title(prompt: str) -> str:
    shortened_prompt = ' '.join(prompt.split())
    if len(shortened_prompt) <= 48:
        return shortened_prompt

    return f'{shortened_prompt[:45].rstrip()}...'
