\set ON_ERROR_STOP on
DO $$ BEGIN
    IF (SELECT count(*) FROM messages) <> 5
    THEN RAISE EXCEPTION 'Wrong remaining message count'; END IF;
    IF (SELECT count(*) FROM messages WHERE user_id =
        '00000000-0000-0000-0000-000000000007') <> 3
    THEN RAISE EXCEPTION 'Real user messages changed'; END IF;
    IF (SELECT demo_question_count FROM users WHERE whatsapp_user_id = 'demo-test-a') <> 16
       OR (SELECT demo_question_count FROM users WHERE whatsapp_user_id = 'demo-test-b') <> 17
    THEN RAISE EXCEPTION 'Demo display counts changed'; END IF;
    IF (SELECT sum(count) FROM dashboard_daily_counts WHERE kind = 'questions') <> 5
    THEN RAISE EXCEPTION 'Daily counts stale'; END IF;
END $$;
SELECT 'Demo compaction and real-data preservation checks passed' AS result;
