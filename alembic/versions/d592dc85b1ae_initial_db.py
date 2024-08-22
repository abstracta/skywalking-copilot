"""Initial DB

Revision ID: d592dc85b1ae
Revises: 
Create Date: 2024-08-22 15:26:52.237685

"""
from typing import Sequence, Union

from langchain_postgres import PostgresChatMessageHistory
from alembic import op
import sqlalchemy as sa

from skywalking_copilot.database import CHAT_HISTORY_TABLE

# revision identifiers, used by Alembic.
revision: str = 'd592dc85b1ae'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('sessions',
                    sa.Column('id', sa.String(), nullable=False),
                    sa.Column('locales', sa.String(), nullable=False),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('questions',
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
    op.drop_table('sessions')
