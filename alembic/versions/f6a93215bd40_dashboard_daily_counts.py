"""Maintain exact daily counts so dashboard reads do not scan message history."""

from alembic import op

revision = "f6a93215bd40"
down_revision = "c8d17432a910"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Serialize the initial backfill with writers; triggers and totals commit together.
    op.execute("LOCK TABLE users, messages IN SHARE ROW EXCLUSIVE MODE")
    op.execute("""
        CREATE TABLE dashboard_daily_counts (
            kind text NOT NULL,
            day date NOT NULL,
            count bigint NOT NULL,
            PRIMARY KEY (kind, day)
        )
    """)
    op.execute("""
        INSERT INTO dashboard_daily_counts
        SELECT 'users', (first_seen_at AT TIME ZONE 'Asia/Kolkata')::date, count(*)
        FROM users GROUP BY 2
    """)
    op.execute("""
        INSERT INTO dashboard_daily_counts
        SELECT 'questions', (created_at AT TIME ZONE 'Asia/Kolkata')::date, count(*)
        FROM messages WHERE direction = 'INBOUND' GROUP BY 2
    """)
    op.execute("""
        CREATE FUNCTION maintain_dashboard_daily_counts() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            metric text;
            old_day date;
            new_day date;
        BEGIN
            IF TG_TABLE_NAME = 'users' THEN
                metric := 'users';
                IF TG_OP <> 'INSERT' THEN
                    old_day := (OLD.first_seen_at AT TIME ZONE 'Asia/Kolkata')::date;
                END IF;
                IF TG_OP <> 'DELETE' THEN
                    new_day := (NEW.first_seen_at AT TIME ZONE 'Asia/Kolkata')::date;
                END IF;
            ELSE
                metric := 'questions';
                IF TG_OP <> 'INSERT' AND OLD.direction = 'INBOUND' THEN
                    old_day := (OLD.created_at AT TIME ZONE 'Asia/Kolkata')::date;
                END IF;
                IF TG_OP <> 'DELETE' AND NEW.direction = 'INBOUND' THEN
                    new_day := (NEW.created_at AT TIME ZONE 'Asia/Kolkata')::date;
                END IF;
            END IF;
            IF old_day IS NOT DISTINCT FROM new_day THEN
                RETURN NULL;
            END IF;
            IF old_day IS NOT NULL THEN
                UPDATE dashboard_daily_counts SET count = count - 1
                WHERE kind = metric AND day = old_day;
            END IF;
            IF new_day IS NOT NULL THEN
                INSERT INTO dashboard_daily_counts VALUES (metric, new_day, 1)
                ON CONFLICT (kind, day) DO UPDATE
                    SET count = dashboard_daily_counts.count + 1;
            END IF;
            RETURN NULL;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER dashboard_users_counts
            AFTER INSERT OR DELETE OR UPDATE OF first_seen_at ON users
            FOR EACH ROW EXECUTE FUNCTION maintain_dashboard_daily_counts()
    """)
    op.execute("""
        CREATE TRIGGER dashboard_questions_counts
            AFTER INSERT OR DELETE OR UPDATE OF created_at, direction ON messages
            FOR EACH ROW EXECUTE FUNCTION maintain_dashboard_daily_counts()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER dashboard_questions_counts ON messages")
    op.execute("DROP TRIGGER dashboard_users_counts ON users")
    op.execute("DROP FUNCTION maintain_dashboard_daily_counts()")
    op.execute("DROP TABLE dashboard_daily_counts")
