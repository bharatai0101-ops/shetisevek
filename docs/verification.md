# Local verification record

Verified on Windows with Python **3.10.0** and an isolated **PostgreSQL 18** cluster listening only on `127.0.0.1:55439`. This cluster was created for this task under the workspace tooling directory; the pre-existing PostgreSQL service/database was not modified. No live Meta or Gemini requests were made by the tests.

| Command / check | Actual result |
| --- | --- |
| `uv sync --python <installed Python310/python.exe>` | Installed the project and 58 resolved packages into `.venv` |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; 107 Python files formatted |
| `mypy app` | Passed; no issues in 81 source files |
| `pytest -q --tb=short` with `TEST_DATABASE_URL` | **67 passed**, no skips; final run 16.65 seconds |
| `alembic revision --autogenerate -m initial_schema` | Generated `de42c1dc74c5_initial_schema.py`; reviewed and corrected deferred FK handling |
| `alembic upgrade head` | Applied successfully to real PostgreSQL |
| `alembic downgrade base` then `alembic upgrade head` | Successful round trip on the isolated test database |
| `alembic check` | Passed; no new upgrade operations detected |
| Import `app.main.app` and `configure_mappers()` | Passed; application and ORM relationships import/configure successfully |
| `uv pip check --python .venv/Scripts/python.exe` | All 58 installed packages compatible |
| `docker compose config --quiet` | Passed using a local copy of `.env.example` |
| Docker engine connectivity | Unavailable: Docker Desktop Linux engine named pipe was absent |

The test suite covers authentication, exact-byte signatures, malformed/multiple/unsupported events, request limits, database failures, users/profiles/conversations, message/job persistence, duplicate and overlapping deliveries, concurrency, lost/stale claims, generation mapping/errors, delivery retries without regeneration, uncertain sends, receipt ordering/reconciliation, explicit profile/crop writes, Marathi follow-up context, safe logging and configuration validation. Provider responses are mocked; one test constructs and closes the real GenAI SDK client without sending requests.

Not verified locally: a Docker image build or running containers, production HTTPS/tunnel setup, actual Meta account permissions/phone registration, a live Gemini answer or its agricultural quality, live Marathi response fidelity, actual WhatsApp delivery/read receipts, hosted GitHub Actions execution, production load/capacity, or an operator's backup/restore infrastructure. These require the corresponding environment and account configuration.

The `.env` file is an ignored copy of the template with provider secrets still blank. It is not a working production configuration. Fill it before starting the application. Documentation contains the required settings and account setup steps.
