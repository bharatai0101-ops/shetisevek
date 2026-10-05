"""Cover dashboard counts and recent-user ordering without blocking writes."""

from alembic import op

revision = "c8d17432a910"
down_revision = "be4ef1c74335"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_direction_created_at "
            "ON messages (direction, created_at) INCLUDE (id)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_users_recent_activity "
            "ON users (last_seen_at DESC, first_seen_at DESC, id)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_users_registration "
            "ON users (first_seen_at DESC, id)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name in (
            "ix_users_registration",
            "ix_users_recent_activity",
            "ix_messages_direction_created_at",
        ):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
