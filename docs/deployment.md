# Deployment and operations

## Release procedure

1. Run CI with Python 3.10 and PostgreSQL. Review dependency/security updates, migration SQL, provider configuration and multilingual agricultural acceptance cases.
2. Build the multi-stage image. Runtime requirements are exact-version/hash locked; API and worker use the same image. Pin the resulting image digest in your deployment.
3. Supply required credentials using your secret manager and set `APP_ENV=production`, `DEBUG=false`. Use separate deployment/runtime database roles where practical; the runtime role needs table DML and sequence access, migrations need DDL privileges.
4. Back up PostgreSQL and verify restore procedures. Run **one** migration release job: `alembic upgrade head`, then `alembic check`. Do not let every replica race schema changes.
5. Start API replicas and worker replicas separately. Place HTTPS/load balancing in front of the API. Remove Compose's fixed API host-port mapping when scaling API containers and route through the service network. No sticky sessions are needed.
6. Point Meta at the HTTPS callback and perform the real acceptance flow described in the README. Automated tests do not validate your actual credentials, sender registration, Gemini model availability or answer quality.

## Compose

```bat
copy .env.example .env
rem Fill credentials before continuing.
docker compose config --quiet
docker compose up --build -d
docker compose logs -f api worker
docker compose up -d --scale worker=3
```

Compose runs PostgreSQL with a named persistent volume and readiness check, a one-shot Alembic service, API and worker. PostgreSQL 18's volume is mounted at `/var/lib/postgresql`. API/worker run as UID 10001, use read-only root filesystems and writable `/tmp`. `stop_grace_period` allows current bounded network work to finish. Avoid `docker compose down -v`: it removes stored data. For a local PostgreSQL already listening on 5432, change the Compose host binding or use the existing server with a dedicated database.

The local Compose setup publishes database/API ports only on loopback. Production should keep PostgreSQL private and use application-level database credentials with required privileges. A managed PostgreSQL service is compatible; the application does not require a vendor-specific API.

## Concurrency and shutdown

Direct database connections or session-mode PgBouncer are required. Transaction pooling cannot preserve session advisory locks. Each worker occupies one database connection while a job is active, but does not keep a transaction open across Gemini/Meta calls. Size PostgreSQL connection budgets for API pools and worker replicas.

SIGTERM/SIGINT stop polling and allow current work to finish before HTTP/SDK clients and the engine close. Abrupt termination leaves a stale claim that another worker can reclaim after `JOB_STALE_SECONDS`. A surviving database session lock still prevents concurrent generation. A persisted send-intent marker requires receipt/operator reconciliation before replay.

## Monitoring

`GET /health` is liveness; `GET /ready` checks database connectivity and an applied Alembic revision. CI's `alembic check` detects model/schema drift. Neither health endpoint calls paid providers. Worker health uses a local temporary heartbeat after successful database iterations; it is a liveness indicator, not proof of job completion.

Alert on queue age, repeated retries, `FAILED` jobs, `delivery_uncertain`, stale locks, unprocessed status events, API 5xx, worker restarts, database connections/disk, provider quotas and cost. Use structured request/event/job/message/internal-user IDs for correlation. Do not log full messages or credentials for routine monitoring.

## Recovering jobs

Inspect from a trusted database console:

```sql
SELECT id, message_id, status, attempts, max_attempts, last_error, locked_at
FROM processing_jobs WHERE status IN ('FAILED','PROCESSING') ORDER BY created_at;
```

For ordinary permanent failures (for example credentials/model configuration), fix the cause before requeuing. Lock the job in an operator transaction, verify no worker is processing it, then set `status='RETRY'`, reset attempts if a new bounded attempt budget is intended, set `available_at=now()`, and clear lock fields. Replaying an old turn after newer replies have completed can affect conversation order; inspect the conversation first.

**Do not blindly requeue `delivery_uncertain`.** The message may already have reached the farmer. Look for a receipt whose `payload->>'biz_opaque_callback_data'` equals the outbound message UUID, or whose provider ID matches Meta's records. Correlated incoming statuses automatically reconcile. If acceptance/delivery is confirmed through trusted operator evidence, transactionally store the provider ID and timestamps and mark the job completed. If non-delivery is conclusively confirmed, clear the outbound `send_started_at`, set the message to `GENERATED`, and requeue the existing job; the saved text is reused. If the outcome remains unknown, retain the block rather than risk an automatic duplicate.

Receipts reporting a provider delivery failure complete the send job and mark the message failed; they do not automatically generate or resend another answer. Investigation can distinguish API acceptance from actual delivery. Jobs outside the conservative 23-hour free-form window fail instead of sending; approved-template flows require a separate implementation.

## Dependency updates

Maintain `pyproject.toml`, `uv.lock` and both hash exports together:

```bat
uv lock --upgrade
uv sync --locked --python 3.10
uv export --frozen --no-dev --no-emit-project --no-editable -o requirements.lock
uv export --frozen --no-emit-project --no-editable -o requirements-dev.lock
python -m ruff check .
python -m ruff format --check .
python -m mypy app
python -m pytest
python -m alembic check
```

Keep backups and practice rollback on staging. Downgrades can destroy data and are not the default production rollback strategy; prefer a reviewed forward fix or application rollback compatible with the expanded schema.
