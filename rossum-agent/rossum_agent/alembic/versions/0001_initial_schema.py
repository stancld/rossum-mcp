"""Initial schema: chats and chat_files tables.

Revision ID: 0001
Revises:
Create Date: 2026-03-19

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BYTEA, JSONB

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chats",
        sa.Column("user_id", sa.Text, nullable=False, server_default=""),
        sa.Column("chat_id", sa.Text, nullable=False),
        sa.Column("messages", JSONB, nullable=False, server_default="[]"),
        sa.Column("output_dir", sa.Text, nullable=True),
        sa.Column("metadata_", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "chat_id"),
        if_not_exists=True,
    )
    op.create_index("idx_chats_expires_at", "chats", ["expires_at"], if_not_exists=True)

    op.create_table(
        "chat_files",
        sa.Column("chat_id", sa.Text, nullable=False),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("content", BYTEA, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("chat_id", "filename"),
        if_not_exists=True,
    )
    op.create_index("idx_chat_files_expires_at", "chat_files", ["expires_at"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("idx_chat_files_expires_at", table_name="chat_files")
    op.drop_table("chat_files")
    op.drop_index("idx_chats_expires_at", table_name="chats")
    op.drop_table("chats")
