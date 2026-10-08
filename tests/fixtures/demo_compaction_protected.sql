\set ON_ERROR_STOP on
INSERT INTO messages
    (id, user_id, conversation_id, direction, role, message_type, status, raw_payload)
VALUES (md5('extra-protected-test')::uuid,
        '00000000-0000-0000-0000-000000000005',
        '00000000-0000-0000-0000-000000000005',
        'INBOUND', 'USER', 'TEXT', 'RECEIVED', '{"demo":true}');
INSERT INTO farmer_crops (id, user_id, crop_name, status, source_message_id)
VALUES (md5('protected-test-crop')::uuid,
        '00000000-0000-0000-0000-000000000005', 'Test crop', 'ACTIVE',
        md5('00000000-0000-0000-0000-000000000005:3')::uuid);
