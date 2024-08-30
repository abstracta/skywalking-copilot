"""Initial DB

Revision ID: 99989526150b
Revises: 
Create Date: 2024-08-30 15:55:28.662664+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from langchain_postgres import PostgresChatMessageHistory

from skywalking_copilot.database import CHAT_HISTORY_TABLE

# revision identifiers, used by Alembic.
revision: str = '99989526150b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('locales', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'alarm_events',
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('alarm_id', sa.String(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('service', sa.String(), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.PrimaryKeyConstraint('session_id', 'alarm_id', 'service')
    )
    op.create_table(
        'questions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('question', sa.String(), nullable=False),
        sa.Column('answer', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    PostgresChatMessageHistory.create_tables(op.get_bind().connection.driver_connection, CHAT_HISTORY_TABLE)


def downgrade() -> None:
    PostgresChatMessageHistory.drop_table(op.get_bind().connection.driver_connection, CHAT_HISTORY_TABLE)
    op.drop_table('questions')
    op.drop_table('alarm_events')
    op.drop_table('sessions')
