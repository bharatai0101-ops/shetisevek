# Demo question storage

Demo users (`whatsapp_user_id` starting with `demo-`) keep one sample inbound
question. Their sample activity number lives in `users.demo_question_count`,
separately from the number of physical messages. Real users continue to show
their actual inbound question count.

The saved display count preserves the previous frontend calculation: the maximum
of the actual count, any previously saved count, and `11 + (UUID low 32 bits % 20)`.
Question/dashboard totals continue to count physical inbound messages, not the
sample display counts.

New demo growth inserts one question and saves its display count. The shared
sample generator skips users who already have a sample question, including when
called with `additional=True`.

## Existing data maintenance

Apply Alembic revision `a71d9c03e452` first. After taking a verified full database
backup, stop API/worker writes and run `scripts/compact_demo_questions.sql` with
`psql`. Restart the services after the maintenance transaction finishes.

The script saves display counts before deleting extra sample inbound questions.
It requires both a demo user identity and `raw_payload.demo = true`; it preserves
all messages owned by real users, even sample-tagged messages. It keeps the newest
sample per demo user and refuses deletion if a candidate has processing-job,
crop-source or reply references. Daily question counts are rebuilt atomically.
For the bulk delete only, per-row triggers are suppressed after all incoming
references are checked under table locks. Unknown reference types abort cleanup.
Normal trigger mode is restored and referencing records are rechecked before
commit. The script can be run again safely. It requires a PostgreSQL administrator
connection for this maintenance step.
The bulk delete temporarily uses 512 MiB working memory to prevent repeated disk
hash-join batches; verify available RAM before running it on another host. This
setting is local to the transaction and does not change server configuration.

Deleting rows makes space reusable inside PostgreSQL. It does not automatically
reduce the provisioned disk size or the EC2 bill. Ordinary vacuum can reclaim dead
tuples for reuse; a separate reviewed operation is needed to return table space
to the filesystem.
After committing cleanup, `scripts/reclaim_demo_question_space.sql` can reclaim
message-table disk space during the same offline maintenance window. Check free
disk space first; it rebuilds the remaining table and its indexes.

The cleanup was tested against an isolated PostgreSQL database using
`tests/fixtures/demo_compaction_seed.sql` and
`tests/fixtures/demo_compaction_verify.sql` around the cleanup script. The fixture
includes a real user with a sample-tagged message to check that it survives.

## Live verification, 8 October 2026

- Removed 10,246,670 extra demo questions; one sample remains per demo user.
- Read-only verification after restart: 1,025,002 physical inbound questions,
  132 real inbound/outbound message records preserved, and maximum one sample
  question per demo user. Auto growth continues, so totals change after this check.
- Users API sample display counts remained 11–30; real counts use actual messages.
- Database size dropped from 9,641 MB to 1,610 MB after message-table compaction.
- API, worker and PostgreSQL were healthy after maintenance.
- Full backups: `/home/ubuntu/before-demo-compaction-final-20261008.dump` and
  `/home/ubuntu/before-demo-compaction-retry-20261008.dump`.
- Initial slow attempts rolled back; the committed operation used the documented
  transaction-local bulk-delete memory setting. No global DB settings changed.
