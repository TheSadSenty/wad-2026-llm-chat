from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.__main__ import create_app
from app.db import get_db_session
from app.models.base import Base
from app.models.user import User
from app.services.security import verify_password


@pytest.fixture()
def client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    testing_session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    application = create_app(init_database=False)

    def override_session() -> Iterator[Session]:
        session = testing_session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db_session] = override_session

    with TestClient(application) as test_client:
        yield test_client, testing_session_factory


def test_registration_form_is_available(client: tuple[TestClient, sessionmaker[Session]]) -> None:
    test_client, _ = client
    response = test_client.get('/register')

    assert response.status_code == 200
    assert 'Create account' in response.text


def test_user_can_register(client: tuple[TestClient, sessionmaker[Session]]) -> None:
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

    with session_factory() as session:
        stored_user = session.query(User).filter_by(login='user@example.com').one()

    assert stored_user.password_hash != 'correct-horse-battery-staple'
    assert verify_password('correct-horse-battery-staple', stored_user.password_hash)


def test_duplicate_email_is_rejected(client: tuple[TestClient, sessionmaker[Session]]) -> None:
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
