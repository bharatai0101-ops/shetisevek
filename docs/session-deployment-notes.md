# Deployment session notes — 4 October 2026

## Confirmed outcome

- Backend deployed to AWS EC2 using Docker Compose.
- PostgreSQL, API, and worker were healthy; migrations exited successfully.
- HTTPS configured through Nginx and Certbot.
- Frontend prepared for AWS Amplify SSR hosting.
- Meta app published, webhook configured, and WhatsApp replies confirmed working by the user.
- The final no-reply issue was caused by the WABA “Subscribe webhooks” toggle being OFF. Enabling it and sending a new message resolved the issue.

## Addresses and repositories

- EC2 Elastic IP: `13.210.39.156`.
- Backend: `https://shetisevakai.duckdns.org`.
- Webhook: `https://shetisevakai.duckdns.org/api/v1/webhooks/whatsapp`.
- Backend repository: `https://github.com/bharatai0101-ops/shetisevek.git`.
- Frontend: `https://main.d3itpv96o6jr46.amplifyapp.com`.
- Frontend repository: `https://github.com/sharad8855/krishi-whisperer.git`.
- Public policy pages: `/privacy` and `/data-deletion` on the frontend.
- Support contact used on policy pages: `shetisevak0202@gmail.com`.
- Current Meta app ID: `1650250790125744`.
- Current Meta phone number ID: `1420896194430705`.
- Current WABA ID: `1101253989121515`.
- Registered business phone: `+91 73877 62401`.

## Connect and deploy manually

From Windows PowerShell:

```powershell
ssh -i "C:\Users\Baap\Downloads\shetisevak-key.pem" ubuntu@13.210.39.156
```

On EC2:

```bash
cd ~/shetisevek
git pull --ff-only
sudo docker compose up -d --build
sudo docker compose ps -a
curl -f https://shetisevakai.duckdns.org/ready
```

Do not overwrite server changes if Git reports conflicts. Dockerfile and Swagger changes were made manually on the server; their inclusion in the backend GitHub repository was not verified during this session.

After updating `.env`, recreate API and worker to load settings:

```bash
sudo docker compose up -d --force-recreate api worker
```

Logs:

```bash
sudo docker compose logs --since=5m --tail=100 api worker
```

Containers continue running after closing SSH/PowerShell. Keep the EC2 instance running. Never use `docker compose down -v` unless database deletion is intended.

## Fixes and configuration

- SSH private key filename is `shetisevak-key.pem`. Windows permissions were restricted to the current user to resolve “unprotected private key file”.
- Dockerfile build initially failed with pip 23.0.1 resolving hashed `google-auth[requests]`. Upgrading pip inside the build virtual environment before installing `requirements.lock` fixed the build.
- Swagger was originally disabled. Server `app/main.py` was changed to `docs_url="/docs"` and `openapi_url="/openapi.json"`.
- DuckDNS points to the Elastic IP. Nginx proxies to `127.0.0.1:8000`; PostgreSQL binds to loopback. Certbot configured HTTPS and automatic renewal.
- EC2 is in `ap-southeast-2`, running Ubuntu 26.04, with about 2 GiB RAM and a 6.7 GiB root filesystem observed during this session. Disk enlargement remains advisable as images and database data grow.
- Jenkins was discussed and declined; deployment remains manual.
- Meta callback verification, the `messages` field subscription, and WABA subscription are separate checks. App publication was required by the console for production webhook delivery.

## Frontend commits pushed

- `d3d3ba7`: Amplify SSR configuration, private runtime environment preparation, deployment notes.
- `6257ae3`: Missing npm lock entries repaired; npm 10.9.9 clean-install dry-run passed.
- `574b7a7`: Public privacy/deletion routes and footer links. Build, targeted lint, and local HTTP page checks passed.

Amplify uses Node.js 22, the Nitro `aws-amplify` preset, and `.amplify-hosting` artifacts. Set `BACKEND_URL`, `ADMIN_API_TOKEN`, and `SESSION_SECRET` in Amplify. The admin token must match the backend; session secret must be at least 32 characters. No `VITE_` prefix for server secrets.

Secrets were kept out of Git. Some credentials were shared in chat and rotation was recommended; completion of rotation was not verified. Do not copy chat credentials into documentation.

## User preference

Communicate in Romanized Marathi/Minglish. For console or terminal guidance, give one step or command at a time and inspect the result before continuing.
