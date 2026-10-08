-- Run only after a verified full backup and the demo display-count migration.
-- API/worker should be stopped for this maintenance transaction.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '30s';
SET LOCAL statement_timeout = '30min';
LOCK TABLE users, messages, processing_jobs, farmer_crops IN SHARE ROW EXCLUSIVE MODE;

CREATE TEMP TABLE compact_real_baseline ON COMMIT DROP AS
SELECT id FROM messages
WHERE (raw_payload->>'demo') IS DISTINCT FROM 'true'
   OR user_id IN (SELECT id FROM users WHERE whatsapp_user_id NOT LIKE 'demo-%');
ALTER TABLE compact_real_baseline ADD PRIMARY KEY (id);

CREATE TEMP TABLE compact_demo_counts ON COMMIT DROP AS
SELECT u.id,
       greatest(coalesce(u.demo_question_count, 0), count(m.id),
           11 + (('x' || right(replace(u.id::text, '-', ''), 8))::bit(32)::bigint % 20))
           AS display_count
FROM users u LEFT JOIN messages m ON m.user_id = u.id AND m.direction = 'INBOUND'
WHERE u.whatsapp_user_id LIKE 'demo-%'
GROUP BY u.id;
ALTER TABLE compact_demo_counts ADD PRIMARY KEY (id);

CREATE TEMP TABLE compact_remove ON COMMIT DROP AS
SELECT id FROM (
    SELECT m.id, row_number() OVER (
        PARTITION BY m.user_id ORDER BY m.created_at DESC, m.sequence DESC
    ) AS position
    FROM messages m JOIN users u ON u.id = m.user_id
    WHERE u.whatsapp_user_id LIKE 'demo-%'
      AND m.direction = 'INBOUND' AND m.raw_payload->>'demo' = 'true'
) ranked WHERE position > 1;
ALTER TABLE compact_remove ADD PRIMARY KEY (id);

-- Refuse to delete any sample referenced by processing, replies or crop records.
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint c
        WHERE c.contype = 'f' AND c.confrelid = 'messages'::regclass
          AND (cardinality(c.conkey) <> 1 OR NOT EXISTS (
              SELECT 1 FROM pg_attribute a
              WHERE a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
                AND (c.conrelid = 'processing_jobs'::regclass AND a.attname = 'message_id'
                  OR c.conrelid = 'farmer_crops'::regclass AND a.attname = 'source_message_id'
                  OR c.conrelid = 'messages'::regclass AND a.attname = 'reply_to_id')
          ))
    ) THEN RAISE EXCEPTION 'Unknown message reference: cleanup rolled back'; END IF;
    IF EXISTS (SELECT 1 FROM processing_jobs j JOIN compact_remove r ON j.message_id = r.id)
       OR EXISTS (SELECT 1 FROM farmer_crops c JOIN compact_remove r ON c.source_message_id = r.id)
       OR EXISTS (SELECT 1 FROM messages m JOIN compact_remove r ON m.reply_to_id = r.id)
    THEN RAISE EXCEPTION 'Protected message reference: cleanup rolled back'; END IF;
END $$;

UPDATE users u SET demo_question_count = c.display_count
FROM compact_demo_counts c WHERE c.id = u.id
AND u.demo_question_count IS DISTINCT FROM c.display_count;

-- All incoming references were checked above while every referencing table is locked.
-- Suppress redundant per-row trigger checks for this bulk deletion only. Recheck
-- referential integrity and rebuild daily counts before commit; restore normal mode.
ANALYZE compact_remove;
-- Prevent the ten-million-ID hash join from spilling into hundreds of batches.
-- This applies only to this maintenance transaction on the verified 4 GiB host.
SET LOCAL work_mem = '512MB';
SET LOCAL enable_nestloop = off;
SET LOCAL session_replication_role = replica;
DELETE FROM messages m USING compact_remove r WHERE m.id = r.id;
SET LOCAL session_replication_role = origin;
SET LOCAL enable_nestloop = on;
SET LOCAL work_mem = '4MB';
DELETE FROM dashboard_daily_counts WHERE kind = 'questions';
INSERT INTO dashboard_daily_counts
SELECT 'questions', (created_at AT TIME ZONE 'Asia/Kolkata')::date, count(*)
FROM messages WHERE direction = 'INBOUND' GROUP BY 2;

DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM processing_jobs j LEFT JOIN messages m ON m.id = j.message_id
        WHERE m.id IS NULL
    ) OR EXISTS (
        SELECT 1 FROM farmer_crops c LEFT JOIN messages m ON m.id = c.source_message_id
        WHERE c.source_message_id IS NOT NULL AND m.id IS NULL
    ) OR EXISTS (
        SELECT 1 FROM messages r LEFT JOIN messages m ON m.id = r.reply_to_id
        WHERE r.reply_to_id IS NOT NULL AND m.id IS NULL
    ) THEN RAISE EXCEPTION 'Message foreign key verification failed: cleanup rolled back'; END IF;
    IF EXISTS (
        SELECT 1 FROM compact_real_baseline b LEFT JOIN messages m ON m.id = b.id
        WHERE m.id IS NULL
    ) THEN RAISE EXCEPTION 'Real message missing: cleanup rolled back'; END IF;
    IF EXISTS (
        SELECT m.user_id FROM messages m JOIN users u ON u.id = m.user_id
        WHERE u.whatsapp_user_id LIKE 'demo-%'
          AND m.direction = 'INBOUND' AND m.raw_payload->>'demo' = 'true'
        GROUP BY m.user_id HAVING count(*) > 1
    ) THEN RAISE EXCEPTION 'Multiple demo questions remain: cleanup rolled back'; END IF;
    IF EXISTS (
        SELECT 1 FROM compact_demo_counts c JOIN users u ON u.id = c.id
        WHERE u.demo_question_count <> c.display_count
    ) THEN RAISE EXCEPTION 'Display counts changed: cleanup rolled back'; END IF;
END $$;
SELECT count(*) AS removed_demo_questions FROM compact_remove;
COMMIT;
SELECT count(*) AS stored_questions FROM messages WHERE direction = 'INBOUND';
