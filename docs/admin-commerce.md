# Deals and finance integration

The frontend server proxies calls to FastAPI. Browser bundles receive neither ADMIN_API_TOKEN nor finance credentials. Configure the backend `.env` with ADMIN_API_TOKEN, FINANCE_EMAIL and FINANCE_PASSWORD. Configure frontend `.env.local` (or server environment in production) with BACKEND_URL, the matching ADMIN_API_TOKEN and a random SESSION_SECRET of at least 32 characters. Restart servers after changing secrets. Vite loads local server settings during development; production must inject them into the server process.

Finance login validates the fixed email/password against backend environment settings. It creates an eight-hour signed access token, stored only in the frontend's encrypted HTTP-only session cookie. Finance report calls require both the admin service token and finance token. Logout clears the browser session. Changing FINANCE_PASSWORD invalidates existing finance tokens. Local HTTP uses a non-secure cookie; production uses a secure cookie and requires HTTPS. The main admin area retains its existing access behavior; the finance login is separate.

## API

All endpoints below require X-Admin-Token:

- GET /api/v1/admin/deals: deals, company details, redemption totals, regions and summary.
- POST /api/v1/admin/deals: validated deal creation.
- PUT /api/v1/admin/deals/{id}: update deal and company fields.
- DELETE /api/v1/admin/deals/{id}: remove deal and its redemption history.
- POST /api/v1/admin/finance/login: environment email/password to finance token.
- GET /api/v1/admin/finance/report: requires X-Finance-Token as well.

Deal status derives from India calendar dates and configured Active/Paused/Draft status. End dates include the entire last day. Summary counts exclude expired, future, paused and draft offers; recent redemptions cover today plus the previous 29 calendar days. Partner payouts due include unpaid payout ledger rows.

Revenue is the sum of revenue amounts. Expense totals include amount plus tax. Net margin subtracts that total from revenue. The API separately exposes base expense, tax and shares on combined cost; the UI shows expense totals and charts. Reports use the current India month and provide the last 7 days, 8 weeks, 12 months and 5 calendar years. Future ledger entries are excluded. Empty periods appear as zero. Ledger entries use PostgreSQL fixed decimal money columns.

## Local demo data

Run from the backend folder:

```text
python -m alembic upgrade head
python -m scripts.seed_commerce
```

The seeder inserts five clearly marked demo offers, twelve aggregate redemption records, 370 days of revenue and expense entries, and an unpaid partner payout. Deterministic UUIDs prevent duplicates; existing records are preserved. Production environment rejects seeding. The seeder does not send WhatsApp messages or make provider requests. Deals currently manage saved offers; automatic WhatsApp coupon delivery is not implemented.

The integrated pages are `/admin/deals`, `/admin/revenue`, `/admin/users`, and `/admin/questions`. Users and Questions fetch their database-backed APIs every second while mounted, including while the tab is in the background. User totals and active counts are actual database aggregates; the simulated counter and rotating demo activity have been removed. User rows sort by most recent WhatsApp activity. Inbound messages automatically create/update the sender, persist a question/message, and enqueue the worker. Duplicate webhook delivery preserves one message and one question count. Questions list the latest saved messages and generated replies; manual admin replies and agronomist escalation remain unconnected. Meta must deliver signed callbacks to this backend through a public HTTPS URL for live arrivals; localhost alone cannot receive Meta callbacks.

## Dashboard

GET /api/v1/admin/dashboard requires X-Admin-Token. It returns actual user and active-deal totals, 30 daily activity points, six consecutive seven-day growth buckets ending today, and four recently registered farmers. The dashboard polls every second and exports the database metrics as CSV. Weekly growth distinguishes registrations from received WhatsApp questions; these are not completed advisory counts. Finance remains on the separately protected Revenue page.
