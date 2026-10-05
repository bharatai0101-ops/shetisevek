# Security and privacy

## Webhook authentication

The GET verification endpoint compares the configured verification token in constant time and requires subscribe mode/challenge. POST reads a size-bounded raw stream (default 1 MiB), computes HMAC-SHA256 over those exact bytes using the app secret, and compares the full `sha256=...` signature using `hmac.compare_digest`. Re-serialized JSON is never used for authentication. Signature verification happens before payload parsing/database work. WABA and phone IDs are also checked before event processing.

HMAC proves the sender knows the app secret; it does not provide a timestamp freshness guarantee by itself. Database event/message uniqueness makes replay idempotent. Rotate compromised secrets/tokens through a controlled deployment. A TLS reverse proxy should enforce request/connection timeouts and size/rate limits that accommodate legitimate Meta bursts and retry behavior.

## Secrets and errors

Pydantic settings use `SecretStr` and hide validation input values. Production rejects blank required settings and debug mode. `.env` is ignored and not copied into images. Use runtime secret injection for production. API errors contain safe categories and request IDs; provider response bodies and stack traces are not exposed in HTTP responses.

Structured logs allow only approved correlation fields. Application event names are fixed; library messages and exception bodies are not serialized by the JSON formatter. SQLAlchemy hides bound parameters. Full conversations, phone numbers, tokens, database URLs and raw request bodies are not logged by application code. Uvicorn access logs are disabled because verification tokens occur in GET query strings. Configure upstream proxies and log collectors to redact queries and authorization headers as well.

Responses include no-store, nosniff, deny-framing and no-referrer headers on normal/error-handled requests. Terminate trusted HTTPS at your edge and configure HSTS there. Swagger UI at `/docs` and the OpenAPI schema at `/openapi.json` are public; admin endpoints still require authentication. Keep debug and database access private. Docker runs API/worker as non-root with a read-only filesystem, a writable temporary mount, dropped capabilities and no-new-privileges.

## Farmer data

Phone/WhatsApp IDs, profile fields, crops, messages and location/media metadata may be personal information. The database stores complete signed envelopes plus individual payloads for processing and audit; these can contain more personal data than the bounded Gemini prompt. Restrict operational access, encrypt disks/backups, and use verified TLS for remote database connections (configure asyncpg-compatible TLS through your deployment environment/connection settings).

Farmer-provided history/profile/crop content is sent to Google for generation; recipients/replies are sent to Meta for WhatsApp delivery. Explain this processing in your privacy notice and review provider data handling terms. Only explicit structured commands write profile/crop fields; no uncertain AI-extracted location or farm size is silently saved.

No automatic retention/deletion process is enabled. Plan retention, deletion requests and backup expiration before public use. Deleting a user cascades most domain rows but does not erase multi-user raw webhook envelopes; a privacy workflow must redact/expire those separately. There is no unauthenticated deletion/admin endpoint.

## AI limitations

Prompts prohibit fabricated chemical doses, diagnoses presented with false certainty, and invented live weather/prices/schemes. Instructions are not a formal guarantee of model behavior. Evaluate multilingual agricultural outputs with domain experts, include an escalation/contact process appropriate to your deployment, and monitor quality without indiscriminately retaining PII in logs. Untrusted farmer/context text never grants tools or database permissions; Gemini output is used only as a message, not executed as code or SQL.
