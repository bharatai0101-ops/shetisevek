\set ON_ERROR_STOP on
INSERT INTO users (id, whatsapp_user_id, first_seen_at, last_seen_at)
VALUES ('00000000-0000-0000-0000-000000000005', 'demo-test-a', now(), now()),
       ('00000000-0000-0000-0000-000000000006', 'demo-test-b', now(), now()),
       ('00000000-0000-0000-0000-000000000007', '919000000001', now(), now());
INSERT INTO conversations (id, user_id, status, started_at, last_message_at)
SELECT id, id, 'CLOSED', now(), now() FROM users;
INSERT INTO messages
    (id, user_id, conversation_id, direction, role, message_type, status, raw_payload, text_content)
SELECT md5(u.id::text || ':' || n)::uuid, u.id, u.id, 'INBOUND', 'USER', 'TEXT',
       'RECEIVED', jsonb_build_object('demo',
           u.whatsapp_user_id LIKE 'demo-%' OR n = 3), 'Question ' || n
FROM users u CROSS JOIN LATERAL generate_series(
    1, CASE WHEN u.whatsapp_user_id = 'demo-test-b' THEN 2 ELSE 3 END
) n;
