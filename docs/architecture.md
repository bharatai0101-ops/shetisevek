# Architecture and guarantees

Meta → FastAPI → PostgreSQL → durable worker → Gemini → PostgreSQL → Meta.

The API handles only HTTP authentication/validation and durable ingestion. Exact request bytes are HMAC-verified before parsing. The parser iterates every entry, change, message, and status, filters to the configured WABA and phone-number ID, and preserves unsupported media metadata.

One transaction records the envelope, per-event audit records, user/profile, active conversation, inbound message and processing job. Only a committed transaction returns success. User-scoped transaction advisory locks are acquired in sorted order before message ingestion; upserts and unique constraints remain the source of truth. This also avoids deadlocks across overlapping multi-message batches.

Repositories contain database queries; services implement farmer/context/status behavior; routes implement HTTP concerns; provider clients handle network traffic. Prompts are centralized. The API never awaits Gemini and requires neither sticky sessions nor in-memory conversation state.

## Worker claim and ordering

Workers select eligible jobs with `FOR UPDATE SKIP LOCKED`. A correlated anti-join prevents later jobs in a conversation from overtaking pending, retrying, processing, or uncertain earlier work. The worker then obtains a nonblocking PostgreSQL session advisory lock derived from the conversation UUID, commits the claim and holds the connection/lock while processing. Database transactions are short; network calls happen outside transactions.

Each worker handles one job at a time; scale worker processes for concurrency across farmers. Stale `PROCESSING` jobs become eligible after `JOB_STALE_SECONDS`. An old lease alone cannot steal work from a still-connected worker because the session lock remains held. PostgreSQL releases the lock on connection loss; normal cleanup explicitly unlocks before returning a connection to the pool. Use direct PostgreSQL or session pooling, not transaction-mode PgBouncer.

The processing stages are: load context → generate if no saved reply exists → persist reply → commit send intent → send → save provider ID → complete. Ownership and the conversation lock are checked again before saving generation and before sending, so a stale worker that resumes after ownership changes cannot send its answer or overwrite the replacement owner's job state. `reply_to_id` is unique, so a retry reuses the existing answer. `send_started_at` is a persistent ambiguity marker. Stale jobs with this marker and no provider ID become `FAILED/delivery_uncertain` rather than resending. Status callbacks correlate using the outbound UUID placed in `biz_opaque_callback_data` and can complete uncertain jobs.

## Receipt races

Receipts are saved even if the outbound provider ID is not yet available. The callback UUID can match early receipts; after sending, pending receipts for the ID are applied. Workers also sweep now-matchable orphan receipts to cover races between independently committing API and worker transactions. Per-message row locks serialize updates, receipt timestamps are preserved, and delayed sent/delivered events do not regress a read state. Receipt handling never invokes Gemini.

## Conversation context

History is scoped to the conversation and bounded by count and characters. Messages are sorted logically by inbound sequence followed by that inbound's reply, even when later inbound messages were received before the earlier reply was generated. Future queued messages and outbound messages never accepted by Meta are excluded. Profile context is optional; explicit commands update validated structured fields. A future summarizer can augment the context builder without changing the source of truth.

## Honest delivery guarantees

Database idempotency prevents repeated processing caused by duplicate Meta deliveries. It does not make PostgreSQL and provider APIs one atomic system. A crash between a Gemini response and saving that response may repeat generation. A crash or timeout around a Meta send is ambiguous; automatic replay is withheld until receipt or operator reconciliation. Permanent failure is visible in the database and logs. No message is discarded because a provider is down.
