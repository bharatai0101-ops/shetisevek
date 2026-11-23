"""Fill missing mobile numbers from numeric WhatsApp sender IDs."""

from alembic import op

revision = "df41b96e83a2"
down_revision = "a71d9c03e452"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET phone_number = '+' || whatsapp_user_id "
        "WHERE phone_number IS NULL AND whatsapp_user_id ~ '^[1-9][0-9]{6,14}$'"
    )


def downgrade() -> None:
    # Filled values are valid contact data, so keep them on downgrade.
    pass
