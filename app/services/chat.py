from sqlalchemy.orm import Session

from app.models.chat import Chat
from app.models.user import User
from app.repositories.chats import add_chat, add_message, get_chat_for_user, list_chats_for_user


def list_user_chats(*, session: Session, user: User) -> list[Chat]:
    """Return persisted chats for a user."""
    return list_chats_for_user(session, user_id=user.id)


def get_user_chat(*, session: Session, user: User, chat_id: int) -> Chat | None:
    """Return a single chat if the user owns it."""
    return get_chat_for_user(session, chat_id=chat_id, user_id=user.id)


def create_chat_with_mock_reply(*, session: Session, user: User, prompt: str) -> Chat:
    """Create a new chat and persist a mock assistant reply."""
    normalized_prompt = prompt.strip()
    chat = add_chat(
        session,
        user_id=user.id,
        title=_build_chat_title(normalized_prompt),
    )
    add_message(session, chat_id=chat.id, role='user', content=normalized_prompt)
    add_message(session, chat_id=chat.id, role='assistant', content=_generate_mock_reply(normalized_prompt))
    session.commit()
    session.expire_all()
    return get_chat_for_user(session, chat_id=chat.id, user_id=user.id) or chat


def append_mock_reply(*, session: Session, chat: Chat, prompt: str) -> Chat:
    """Append a user message and a mock assistant message to an existing chat."""
    normalized_prompt = prompt.strip()
    add_message(session, chat_id=chat.id, role='user', content=normalized_prompt)
    add_message(session, chat_id=chat.id, role='assistant', content=_generate_mock_reply(normalized_prompt))
    session.commit()
    session.expire_all()
    return get_chat_for_user(session, chat_id=chat.id, user_id=chat.user_id) or chat


def _build_chat_title(prompt: str) -> str:
    shortened_prompt = ' '.join(prompt.split())
    if len(shortened_prompt) <= 48:
        return shortened_prompt

    return f'{shortened_prompt[:45].rstrip()}...'


def _generate_mock_reply(prompt: str) -> str:
    compact_prompt = ' '.join(prompt.split())
    return (
        'Mock assistant reply.\n\n'
        f'I received your message: "{compact_prompt}".\n'
        'A real local GGUF-backed model will replace this mocked response later.\n'
        'For now the flow is fully wired: message submitted, reply generated, and history stored.'
    )
