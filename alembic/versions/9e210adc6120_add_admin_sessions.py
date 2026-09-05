"""Add revocable admin sessions."""

import sqlalchemy as sa

from alembic import op

revision = "9e210adc6120"
down_revision = "4b08cbb499e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_session",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("admin_user_id", sa.Integer(), sa.ForeignKey("admin_user.id"), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("credential_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_admin_session_admin_user_id", "admin_session", ["admin_user_id"])
    op.create_index("ix_admin_session_expires_at", "admin_session", ["expires_at"])


def downgrade() -> None:
    op.drop_table("admin_session")
