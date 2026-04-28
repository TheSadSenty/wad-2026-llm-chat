"""add github oauth identity to users

Revision ID: 9b3c8a4b7f21
Revises: b5e1d2f4c3a1
Create Date: 2026-04-28 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b3c8a4b7f21'
down_revision: Union[str, Sequence[str], None] = 'b5e1d2f4c3a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('github_user_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('github_username', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_users_github_user_id'), 'users', ['github_user_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_users_github_user_id'), table_name='users')
    op.drop_column('users', 'github_username')
    op.drop_column('users', 'github_user_id')
