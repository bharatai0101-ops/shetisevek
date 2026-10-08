"""Store demo display counts independently of physical sample messages."""

import sqlalchemy as sa

from alembic import op

revision = "a71d9c03e452"
down_revision = "f6a93215bd40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("demo_question_count", sa.BigInteger(), nullable=True))
    op.create_check_constraint(
        "nonnegative_demo_question_count", "users", "demo_question_count >= 0"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_nonnegative_demo_question_count"), "users", type_="check")
    op.drop_column("users", "demo_question_count")
