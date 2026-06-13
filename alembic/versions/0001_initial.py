"""initial schema: users + mock_endpoints

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "mock_endpoints",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("delay_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mock_endpoints_id", "mock_endpoints", ["id"])
    op.create_index("ix_mock_endpoints_owner_id", "mock_endpoints", ["owner_id"])
    op.create_index("ix_mock_endpoints_path", "mock_endpoints", ["path"])
    op.create_index("ix_mock_endpoints_method", "mock_endpoints", ["method"])


def downgrade() -> None:
    op.drop_index("ix_mock_endpoints_method", table_name="mock_endpoints")
    op.drop_index("ix_mock_endpoints_path", table_name="mock_endpoints")
    op.drop_index("ix_mock_endpoints_owner_id", table_name="mock_endpoints")
    op.drop_index("ix_mock_endpoints_id", table_name="mock_endpoints")
    op.drop_table("mock_endpoints")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
