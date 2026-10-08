-- Offline, after compact_demo_questions.sql commits and with a verified backup.
-- Requires free disk space for the remaining message table and rebuilt indexes.
\set ON_ERROR_STOP on
SET statement_timeout = '20min';
SET maintenance_work_mem = '256MB';
VACUUM (FULL, ANALYZE) messages;
VACUUM (ANALYZE) users;
SELECT pg_size_pretty(pg_database_size('shetisevek')) AS compacted_database_size;
