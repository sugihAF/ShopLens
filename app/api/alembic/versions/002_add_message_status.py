"""Add status column to messages

Revision ID: 002
Revises: 001
Create Date: 2026-05-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    message_status = sa.Enum(
        'COMPLETE', 'CANCELLED', 'ERROR',
        name='messagestatus',
    )
    message_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'messages',
        sa.Column(
            'status',
            message_status,
            server_default='COMPLETE',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('messages', 'status')
    sa.Enum(name='messagestatus').drop(op.get_bind(), checkfirst=True)
