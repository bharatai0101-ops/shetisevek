# Meta WhatsApp Cloud API setup

This backend uses the official Graph API over HTTPS. No WhatsApp Web session, browser, unofficial library, or personal-account automation is involved.

Meta changes dashboard labels and eligibility flows. The following identifies the required objects and settings; follow the equivalent screen if your app's layout differs. Meta's documentation returned HTTP 429 during local implementation research, so the precise dashboard wording was not verified against an authenticated account.

1. Sign in at [Meta for Developers](https://developers.facebook.com/apps/) and create/select the app associated with your business portfolio. Select the WhatsApp/business-messaging use case offered to your account and configure the WhatsApp product.
2. Open the WhatsApp **API Setup / Getting Started** screen. Select the test business sender or register your intended production business phone number. Record the numeric **Phone number ID** as `META_PHONE_NUMBER_ID` and **WhatsApp Business Account ID** as `META_WHATSAPP_BUSINESS_ACCOUNT_ID`.
3. For Meta's test sender, add and verify the farmer/test recipient in the permitted-recipient list before testing. Complete production number registration/business requirements applicable to your account before using a real sender.
4. Open app **Settings → Basic** (or the application credentials screen), reveal **App Secret**, and store it only as `META_APP_SECRET` in your environment/secret manager.
5. In business settings, create/select a system user, grant access to the app and WhatsApp account assets, and generate an appropriate access token. Messaging requires `whatsapp_business_messaging`; account management/subscription operations require `whatsapp_business_management`. Use the permissions and asset assignments applicable to your integration. Set `META_ACCESS_TOKEN`; do not treat a temporary developer token as production credentials.
6. Set `META_GRAPH_API_VERSION` to a supported version shown in your Meta dashboard/docs, with the leading `v`. There is deliberately no version hardcoded in the application.
7. Generate your own random verification token, for example `python -c "import secrets; print(secrets.token_urlsafe(32))"`, and save it as `META_VERIFY_TOKEN`. This is distinct from the access token and app secret.
8. Deploy the API at a trusted public HTTPS URL, or start a local HTTPS tunnel to port 8000. Run migrations and check `/ready` first.
9. Open WhatsApp **Configuration → Webhooks** (or the app Webhooks screen for the `whatsapp_business_account` object). Enter `https://YOUR-DOMAIN/api/v1/webhooks/whatsapp` as the callback and the exact `META_VERIFY_TOKEN` as the verification token. Choose **Verify and save** or its equivalent. The server returns `hub.challenge` as plain text only when mode/token are correct.
10. Subscribe to the **messages** field. This carries both inbound messages and delivery-status notifications. Ensure your app is subscribed to the intended WABA; the official account endpoint is `POST /{GRAPH_VERSION}/{WABA_ID}/subscribed_apps` with an authorized bearer token. Check the subscription with the corresponding GET endpoint if dashboard test callbacks work but actual messages do not.
11. Run both API and worker. Send `माझ्या कांद्याची पाने पिवळी पडत आहेत` to the configured business number. Confirm an inbound database record, completed job, assistant record, and provider message ID. Then send `पीक 45 दिवसांचे आहे` and check continuity. Observe sent/delivered/read receipts updating that outbound record.

Every POST must include Meta's `x-hub-signature-256`; the signature is an HMAC-SHA256 of the original request bytes using the app secret. A manual dashboard sample or local test missing a valid signature will correctly be rejected. Do not disable this in production.

Outbound requests go to `https://graph.facebook.com/{META_GRAPH_API_VERSION}/{META_PHONE_NUMBER_ID}/messages` with the configured bearer token. A UUID correlation value is sent in `biz_opaque_callback_data` to support status/send races. Free-form replies are limited to recent inbound conversations; the worker uses a conservative 23-hour cutoff. Template creation/sending is not implemented.

References: [Meta WhatsApp documentation](https://developers.facebook.com/documentation/business-messaging/whatsapp/overview), [Meta's official Postman workspace](https://www.postman.com/meta/whatsapp-business-platform/overview), [official webhook payload examples](https://www.postman.com/meta/whatsapp-business-platform/folder/tduohwq/webhook-payload-reference).
