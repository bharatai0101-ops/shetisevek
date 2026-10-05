# ShetiSevek AI

WhatsApp AI Assistant for Farmers

A Python **3.10** backend using FastAPI, SQLAlchemy async ORM, PostgreSQL, the official Meta WhatsApp Cloud API, and Google's official GenAI SDK. It provides durable farming conversations in Marathi, Hindi, English, Hinglish, and Romanized Marathi. Language behavior is instructed through Gemini; it has not been evaluated against a live model in the local automated tests.

The API commits incoming messages and jobs before acknowledging Meta. Independent workers load farmer context and conversation history, generate an answer, save it, send it, and record delivery. There is no in-memory conversation store, unofficial WhatsApp automation, or public administration API.

## Architecture

```mermaid
flowchart TD
    Farmer[Farmer on WhatsApp] --> Meta[Meta WhatsApp Cloud API]
    Meta --> API[FastAPI: HMAC validation and parsing]
    API --> DB[(PostgreSQL: users, profiles, crops, history, events, jobs)]
    API --> ACK[HTTP 200 after commit]
    DB --> Worker[Durable worker replicas]
    Worker --> Gemini[Google GenAI SDK]
    Gemini --> Worker
    Worker --> Saved[Persist generated answer]
    Saved --> DB
    Saved --> Outbound[Meta messages endpoint]
    Outbound --> Farmer
    Meta --> Status[Delivery status webhook]
    Status --> DB
```

See [architecture](docs/architecture.md), [database](docs/database.md), and [deployment](docs/deployment.md) for locking, recovery, and operational guarantees. `docs/folder-tree.txt` contains the generated source tree.

## Prerequisites

- Python 3.10, preferably the newest available 3.10 patch release; Python 3.12 is not required.
- PostgreSQL (local validation used PostgreSQL 18).
- A Meta developer app with WhatsApp Cloud API, a registered phone number, and suitable access token.
- A Google AI Studio project/API key and an available Gemini model.
- A public HTTPS endpoint for Meta webhooks. Docker Desktop with Linux containers is optional for local Python development.

## Windows CMD installation

Open CMD in this folder:

```bat
py -3.10 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps -e .
copy .env.example .env
notepad .env
```

`py -m venv .venv` also works if the launcher defaults to Python 3.10. On PowerShell, activate with `.venv\Scripts\Activate.ps1` or call `.venv\Scripts\python.exe` directly. On Linux/macOS, use `python3.10 -m venv .venv` and `source .venv/bin/activate`; subsequent Python commands are identical.

Dependencies are constrained in `pyproject.toml`, resolved in `uv.lock`, and exported with hashes in `requirements.lock` (runtime) and `requirements-dev.lock` (development/CI). `pip install -e ".[dev]"` is supported for unconstrained development; use the lock files for reproducibility. To deliberately update dependencies, use `uv lock --upgrade`, run the checks, and regenerate both exports as described in [deployment](docs/deployment.md).

## Environment

Fill these required values in `.env`:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://USER:PASSWORD@HOST:5432/shetisevek` |
| `META_VERIFY_TOKEN` | Your own long random webhook verification secret |
| `META_APP_SECRET` | Meta application secret used for webhook HMAC |
| `META_ACCESS_TOKEN` | System-user token authorized to send WhatsApp messages |
| `META_PHONE_NUMBER_ID` | Meta numeric phone-number ID, not the phone number |
| `META_WHATSAPP_BUSINESS_ACCOUNT_ID` | Numeric WhatsApp Business Account (WABA) ID |
| `META_GRAPH_API_VERSION` | Supported version from your Meta dashboard, including `v` |
| `GEMINI_API_KEY` | Google AI Studio API key |
| `GEMINI_MODEL` | Available model name from your Google project |

For Compose also set `POSTGRES_PASSWORD`. Use a URL-safe database password or percent-encode credentials when assembling database URLs; Compose interpolates this value into its URL. `.env` is ignored by Git and excluded from Docker build context. Example credentials are for local development only.

Operational settings include `APP_ENV`, `DEBUG`, `CONVERSATION_HISTORY_LIMIT`, `CONVERSATION_HISTORY_CHAR_LIMIT`, `HTTP_TIMEOUT_SECONDS`, `JOB_POLL_INTERVAL_SECONDS`, `JOB_MAX_ATTEMPTS`, `JOB_STALE_SECONDS`, `WEBHOOK_MAX_BYTES`, and `LOG_LEVEL`. Required values are validated at startup; production rejects `DEBUG=true`. `HOST` and `PORT` are deployment settings: pass matching values to Uvicorn when changing the documented command.

Validate without printing secrets:

```bat
python scripts\check_env.py
```

## PostgreSQL and migrations

Use an existing dedicated PostgreSQL database or start the Compose database:

```bat
docker compose up -d postgres
```

If PostgreSQL already uses host port 5432, use that server with a dedicated `shetisevek` database, or change the Compose host port and your local `DATABASE_URL`. The application uses `localhost` when running in CMD; Compose overrides it to the `postgres` service hostname inside containers.

```bat
python scripts\wait_for_db.py
python -m alembic upgrade head
python -m alembic check
```

The checked-in initial migration is `de42c1dc74c5_initial_schema.py`. Production uses Alembic, never `create_all()`. Future schema changes:

```bat
python -m alembic revision --autogenerate -m "describe change"
rem Review generated SQL, constraints, enum changes and downgrade carefully.
python -m alembic upgrade head
python -m alembic check
```

## Run the two processes

Terminal 1, from this folder with the environment activated:

```bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --no-access-log
```

Terminal 2:

```bat
.venv\Scripts\activate
python -m app.workers.main
```

Check:

```bat
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

`/health` is process liveness. `/ready` checks PostgreSQL and an applied migration revision; it does not test provider credentials or prove worker health. Swagger UI is available at `/docs`, with its OpenAPI schema at `/openapi.json`. Admin endpoints still require their authentication headers.

## Meta and Gemini configuration

Follow the detailed [Meta setup](docs/meta-whatsapp-setup.md) and [Gemini setup](docs/gemini-setup.md).

The callback URL is:

```text
https://YOUR-DOMAIN/api/v1/webhooks/whatsapp
```

GET verifies `hub.mode`, `hub.verify_token`, and `hub.challenge`. POST validates `x-hub-signature-256` against the exact raw bytes using `META_APP_SECRET` and constant-time comparison. `META_VERIFY_TOKEN` is your verification secret; it is **not** the access token.

For local testing, expose port 8000 through your HTTPS tunnel and use its public URL plus the callback path. For example, with an already installed/configured ngrok CLI, `ngrok http 8000`. Update Meta when the public URL changes. Do not use a local HTTP URL in Meta, disable HMAC, or place API keys in the callback URL.

## Conversations, profiles, and crops

All messages and generated answers are stored in PostgreSQL, including failed sends. The same farmer's last 24 hours of saved conversation are reconstructed for every Gemini call in logical order, without the former 20-message cutoff. The configured character budget still bounds model input; unusually long daily chats can exceed it. Existing message/question storage is unchanged; no extra memory table or automatic profile writes are added. `CONVERSATION_HISTORY_LIMIT` is a legacy setting and no longer limits recall. A reply to "पीक 45 दिवसांचे आहे" receives the earlier onion discussion. Future queued turns and undelivered generated answers are excluded from earlier prompts. This is bounded recent memory, not an unlimited summary of every past message.

Each new user gets an optional empty profile and an active conversation without a registration questionnaire. Structured data changes require explicit input; the service does not silently infer a village, farm size, or crop record from uncertain AI extraction. Natural conversation remains available at all times. The following optional text commands save fields through validated services:

```text
/profile {"preferred_language":"Marathi","district":"Pune","soil_type":"black"}
/crop {"crop_name":"onion","season":"rabi","area":1.5,"area_unit":"acre"}
/crop {"crop_name":"tomato","sowing_date":"2026-09-01"}
```

`/profile` updates only supplied fields and accepts `null` to clear one. `/crop` creates a distinct record per explicit command, idempotent when that message is redelivered or its job retries. Multiple crops are supported. There is no unauthenticated profile-management API. Natural-language automatic profile extraction, crop update UI, and conversation summarization are not implemented.

The centralized prompts instruct ShetiSevek AI to follow the farmer's language, avoid repeated welcomes, ask only useful follow-up questions, express diagnostic uncertainty, and never invent chemical doses or live data. Prompt instructions reduce risk but are not a guarantee that a generative model will always comply; perform domain review before public rollout.

## Supported messages and integrations

Text, button text, and interactive reply titles are used for conversation. Image/audio/video/document/location/contact/reaction/unknown events are recognized and preserved, including media IDs and MIME metadata. The model receives an explicit unavailable-media marker and any supplied caption, never fabricated image analysis.

Gemini Google Search grounding is enabled for current weather, market prices, agricultural news and government schemes. The bot asks for missing market/location details, reports data dates and gives short answers without appending source links. Search coverage and freshness are not guaranteed. Dedicated weather, market-price, government-scheme and knowledge providers still have interfaces only; image diagnosis is not connected. See [Gemini setup](docs/gemini-setup.md) for supported-model configuration and live acceptance checks.

## Docker

```bat
docker compose config --quiet
docker compose up --build -d
docker compose logs -f api worker
docker compose ps
```

Compose provides `postgres`, a one-shot `migrate` service, `api`, and `worker`. API and worker use the same non-root multi-stage Python 3.10 image. PostgreSQL has a persistent volume; API/worker filesystems are read-only with temporary storage under `/tmp`. Migrations finish before application startup.

Scale workers using `docker compose up -d --scale worker=3`. For API replicas, remove the single fixed host-port mapping and place a reverse proxy/load balancer in front of the shared service network. No sticky sessions are required. Use direct PostgreSQL or session-mode connection pooling: transaction-mode PgBouncer is incompatible with session advisory locks.

The included Compose configuration is a local deployment baseline. For production, configure trusted HTTPS, network isolation, a secret manager, backups, external monitoring, provider budgets, and a controlled one-shot migration release. See [deployment](docs/deployment.md).

## Tests and quality checks

Unit tests use provider mocks. Integration tests use real PostgreSQL and mocked Meta/Gemini. Never point tests at the production database: integration setup truncates application tables and only accepts database names ending in `_test`.

```bat
python -m ruff check .
python -m ruff format --check .
python -m mypy app
python -m pytest -q
rem To run all integration tests, first create a dedicated test database:
set TEST_DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/shetisevek_test
python -m pytest -q
python -m alembic check
python -c "from app.main import app; print(app.title)"
```

Without `TEST_DATABASE_URL`, database-dependent tests explicitly skip. CI provisions PostgreSQL and runs lint, formatting, strict mypy, tests, migrations, schema-drift checks, and migration downgrade/upgrade. If this folder is nested inside a larger Git repository, place/adapt `.github/workflows/ci.yml` at the repository root and set its working directory to `shetisevek-ai`.

Equivalent Make targets are available: `install`, `dev`, `api`, `worker`, `test`, `lint`, `format`, `typecheck`, `migrate`, `migration`, `docker-up`, `docker-down`. Make is not required on Windows.

## Failure handling and limitations

- Gemini failure retains the inbound message and job; retryable errors use bounded backoff.
- Meta rejection retains the generated answer. Delivery retries reuse that answer, never regenerate it.
- Duplicate delivery is suppressed with event/message/job/reply uniqueness constraints and transactions.
- Workers use `FOR UPDATE SKIP LOCKED`, per-conversation session advisory locks, and stale-claim recovery. A live worker keeps the conversation lock even if a lease becomes old.
- An ambiguous timeout or crash after committed send intent cannot prove whether Meta accepted the message. The job is marked `FAILED` with `delivery_uncertain`, blocks later replies in that conversation, and waits for a correlated status or operator reconciliation. This intentionally avoids an automatic duplicate send.
- Exactly-once calls across PostgreSQL and external APIs cannot be guaranteed. A worker crash after Gemini returns but before saving can repeat generation. Ordinary duplicate webhooks do not cause repeated generation/delivery. Meta sends with uncertain outcomes are not automatically replayed.
- Free-form replies are conservatively stopped when the inbound message is older than 23 hours. Approved-template messaging outside the customer-service window is not implemented.

See [security](docs/security.md) for PII handling and [deployment](docs/deployment.md) for failed-job recovery. Raw payloads and messages are retained until an operator applies an approved retention policy; automatic deletion and summarization are not enabled.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Startup validation failure | Fill every required setting and use numeric Meta IDs and a version like `vNN.N` |
| GET webhook rejected | Verify token, mode, exact callback path, public HTTPS |
| POST rejected | App secret, exact raw-body forwarding, `x-hub-signature-256` |
| Messages saved but no reply | Worker process, job status/age, Gemini model/key/quota, Meta token permissions |
| Job has `delivery_uncertain` | Follow reconciliation instructions; do not blindly requeue |
| `/ready` fails | Database URL, network, credentials, `alembic upgrade head` |
| Tests skipped | Set a dedicated `TEST_DATABASE_URL` ending in `_test` |
| Docker unavailable | Start Docker Desktop/Linux engine; Python development can use local PostgreSQL |
| Text works but images do not diagnose | Image analysis is deliberately not connected |
