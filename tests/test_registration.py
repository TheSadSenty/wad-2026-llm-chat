import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.__main__ import create_app
from app.db import get_db_session
from app.models.base import Base
from app.models.user import User
from app.services.security import verify_password


@pytest.fixture()
def client() -> Iterator[tuple[TestClient, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine(
        'sqlite+aiosqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    testing_session_factory = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare_database())

    application = create_app(init_database=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with testing_session_factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_session

    with TestClient(application) as test_client:
        yield test_client, testing_session_factory

    async def dispose_engine() -> None:
        await engine.dispose()

    asyncio.run(dispose_engine())


def test_registration_form_is_available(client: tuple[TestClient, async_sessionmaker[AsyncSession]]) -> None:
    test_client, _ = client
    response = test_client.get('/register')

    assert response.status_code == 200
    assert 'Create account' in response.text


def test_user_can_register(client: tuple[TestClient, async_sessionmaker[AsyncSession]]) -> None:
    test_client, session_factory = client
    response = test_client.post(
        '/register',
        data={
            'login': 'user@example.com',
            'password': 'correct-horse-battery-staple',
        },
    )

    assert response.status_code == 201
    assert 'registered successfully' in response.text

    async def fetch_user() -> User:
        async with session_factory() as session:
            return (await session.execute(select(User).filter_by(login='user@example.com'))).scalar_one()

    stored_user = asyncio.run(fetch_user())

    assert stored_user.password_hash != 'correct-horse-battery-staple'
    assert verify_password('correct-horse-battery-staple', stored_user.password_hash)


def test_duplicate_email_is_rejected(client: tuple[TestClient, async_sessionmaker[AsyncSession]]) -> None:
    test_client, _ = client
    first_response = test_client.post(
        '/register',
        data={
            'login': 'duplicate@example.com',
            'password': 'password-1',
        },
    )
    second_response = test_client.post(
        '/register',
        data={
            'login': 'duplicate@example.com',
            'password': 'password-2',
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert 'already exists' in second_response.text
