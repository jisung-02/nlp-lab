"""Index public listing and project-publication lookups."""

from alembic import op

revision = "3a472f26e502"
down_revision = "9e210adc6120"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_member_display_created", "member", ["display_order", "created_at"])
    op.create_index("ix_project_created", "project", ["created_at"])
    op.create_index(
        "ix_publication_project_year", "publication", ["related_project_id", "year", "id"]
    )
    op.create_index("ix_post_published_created", "post", ["is_published", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_post_published_created", table_name="post")
    op.drop_index("ix_publication_project_year", table_name="publication")
    op.drop_index("ix_project_created", table_name="project")
    op.drop_index("ix_member_display_created", table_name="member")
