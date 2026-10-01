from sqlalchemy.dialects import postgresql

from app.repositories.job_repository import JobRepository
from app.utils.retry import backoff_seconds


def test_claim_uses_skip_locked_and_conversation_barrier():
    sql = str(JobRepository.claim_statement(180).compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE OF processing_jobs SKIP LOCKED" in sql
    assert "EXISTS" in sql
    assert "conversation_id" in sql
    assert "locked_at" in sql


def test_backoff_is_bounded():
    assert 2 <= backoff_seconds(1) <= 3
    assert 300 <= backoff_seconds(100) <= 301
