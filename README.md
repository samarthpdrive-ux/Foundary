# Foundry — Lost & Found

Foundry is a Flask application for reporting lost and found property and helping people reconnect with their belongings. This workspace currently contains Phases 1–27 of the supplied plan.

## Run locally

From this directory, run:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
$env:FLASK_DEBUG = "1"
py run.py
```

Open <http://127.0.0.1:5000>. The health endpoint is <http://127.0.0.1:5000/health>.

On first development launch, Flask-SQLAlchemy creates the local SQLite database under `instance/lost_found.db`. Configure `SECRET_KEY` before using the application beyond local development. Configure `PUBLIC_BASE_URL` to make printed recovery QR codes work outside the local machine. `MAP_TILE_URL` can point to a permitted tile provider.

## Connect local development to TiDB Cloud

Copy the TiDB Cloud connection details from its **Connect** dialog into `.env`: set `TIDB_HOST`, `TIDB_USER`, `TIDB_PASSWORD`, `TIDB_DATABASE`, and `TIDB_PORT=4000`, and leave `DATABASE_URL` blank. The app builds a `mysql+pymysql` SQLAlchemy connection, safely handles special characters in passwords, verifies the TLS certificate and host name, and enables connection health checks and bounded pooling. `TIDB_SSL_CA` points to the included ISRG Root X1 certificate. TiDB Cloud Starter/Essential usernames include the cluster prefix shown in the Connect dialog.

Run `.\.venv\Scripts\python.exe -m pytest -q` to verify the local workflows and TiDB URL/TLS configuration without requiring a live TiDB account. Start the app locally with `.\.venv\Scripts\python.exe run.py`; the SQLite default keeps local testing self-contained.

## Deploy on Render with TiDB Cloud

The included `render.yaml` defines a Render Blueprint for the Flask web service. Push this project folder to the root of a Git repository, create a Blueprint in Render for that repository, and provide the TiDB host, username, password, and database when prompted. The service applies Alembic migrations before starting Gunicorn and exposes `/health` for health checks. The Blueprint sets the service's Render hostname as its trusted host and configures the public URL for QR links.

In TiDB Cloud, add the Render service's outbound IP ranges to the cluster's IP access list: find them in the Render service's **Connect → Outbound** panel. Avoid opening the database to all IP addresses. Render's outbound ranges depend on the service region; the Blueprint uses Singapore. For database TLS, the application validates both the CA chain and server hostname. TiDB Cloud Starter/Essential requires TLS on public connections. If running locally on Windows and using an explicit CA, download the CA certificate and set its local path in `TIDB_SSL_CA`.

The Blueprint uses Render's free web-service plan for a test deployment. Set the prompted TiDB database value to `foundry`; `sys` is a TiDB system schema. The Blueprint expects the Google Drive Apps Script URL and shared secret described below. This keeps report photos in Drive across Render restarts and redeploys.

## Store report photos in Google Drive

The app resizes and converts each accepted upload to WebP, then sends it through `google_apps_script/Code.gs` into one Drive folder. The database stores the Drive file ID; the app uses that ID to display the image and to remove the file when an image is replaced or its report is deleted. Local uploads remain the default until Drive is configured.

1. Create a dedicated Google Drive folder for Foundry uploads and copy its folder ID from the folder URL.
2. Open [Google Apps Script](https://script.google.com/), create a project, paste in `google_apps_script/Code.gs`, and save it.
3. In **Project Settings → Script properties**, add `DRIVE_FOLDER_ID` with the folder ID and `API_SECRET` with a new random secret of at least 32 characters. Generate one locally with `python -c "import secrets; print(secrets.token_urlsafe(40))"`. Keep this secret private.
4. Deploy as a **Web app**, set **Execute as** to your account, and allow access to **Anyone** (including anonymous users if that is the option shown). Apps Script's `doPost` web app handler uses the deploying account's Drive permission. The secret protects the upload/delete actions. See Google's [web app deployment guide](https://developers.google.com/apps-script/guides/web) and [Drive sharing reference](https://developers.google.com/apps-script/reference/drive/file#setSharing(Access,Permission)).
5. Copy the deployed `/exec` URL. For local development, set these in `.env`:

   ```dotenv
   IMAGE_STORAGE_BACKEND=google_drive
   GOOGLE_DRIVE_WEB_APP_URL=https://script.google.com/macros/s/DEPLOYMENT_ID/exec
   GOOGLE_DRIVE_SHARED_SECRET=the-same-random-secret-as-API_SECRET
   ```

6. For Render, set `GOOGLE_DRIVE_WEB_APP_URL` and `GOOGLE_DRIVE_SHARED_SECRET` when the Blueprint prompts you. `render.yaml` selects `google_drive` for the hosted app; local `.env.example` stays on `local` by default.

Report images are publicly viewable by link because item reports are public in this app. The Drive folder itself does not need public listing; each uploaded image receives viewer access by link. Google Workspace administrators may block anonymous Apps Script deployments or link sharing. Existing local images are not copied to Drive automatically; newly uploaded or replaced images use Drive once configured.


## Production deployment

Set `APP_ENV=production`, a unique random `SECRET_KEY`, `TRUSTED_HOSTS` as a comma-separated list of host names, `DATABASE_URL`, and `RATELIMIT_STORAGE_URI` in the deployment environment. For PostgreSQL, use a SQLAlchemy URL such as `postgresql+psycopg://user:password@host/database`. Production enables secure session cookies and host validation, and it does not create or modify database tables at startup. Apply schema migrations before launching:

```powershell
$env:APP_ENV = "production"
py -m flask --app run.py db upgrade
py run.py
```

The production entry point serves through Waitress on `0.0.0.0:8000` (override with `PORT`). Keep the database and rate-limit storage persistent. In-memory rate-limit storage is suitable for a single local process; use shared storage such as Redis for multi-process deployments. Set HTTPS at the hosting proxy and preserve secure-cookie behavior.

## Tests

Install `requirements-dev.txt` and run `py -m pytest`. The suite exercises public pages, response security headers, authentication and redirect validation, item reporting, claim review, route access, and production configuration validation.

## Phase 20–27 additions

Security hardening includes login and registration throttling, secure production cookies, trusted hosts, response headers, and production secret validation. UI quality includes compact mobile navigation, a skip link, visible keyboard focus, and reduced-motion support. Automated integration coverage exercises core workflows, including TiDB URL and TLS configuration. Deployment supports Waitress locally and Render/Gunicorn with TiDB Cloud or PostgreSQL; production startup expects schema migrations to be applied first. The initial schema and query-index migrations are included. Browse/admin views are paginated, uploads are bounded and compacted, and uploaded images use cache headers.
## Implemented

- **Phase 1 — Setup:** Flask application factory, local config, dependency manifest, starter landing page.
- **Phase 2 — Database:** SQLAlchemy models for users, items, claims, messages, notifications, reports, and possible matches.
- **Phase 3 — Architecture:** application factory, shared extensions, and separate main, authentication, and profile blueprints; admin access decorator.
- **Phase 4 — UI foundation:** shared navigation, footer, flash messages, responsive layout, dark/light theme persistence, form and status styles.
- **Phase 5 — Authentication:** registration, login by email or username, logout, Werkzeug password hashing, CSRF protection, session cookie defaults, and user/admin role field.
- **Phase 6 — Profile:** view/edit profile, password change, report/claim summaries, and personal lost/found/claim lists.
- **Phases 7–8 — Item reports:** authenticated lost/found report creation, editing, closing, optional image uploads, private ownership details, and safe generated image names.
- **Phase 9 — Discovery:** searchable and paginated reports with type, category, approximate location, date, color, brand, and status filters.
- **Phase 10 — Details:** public item detail pages, owner actions, and appropriate claim/report actions.
- **Phase 11 — Matching:** rule-based 0–100 similarity scoring; suggestions at 60% or higher are stored and notify both report owners.
- **Phase 12 — Claims:** private ownership answers, finder review, approve/reject decisions, notifications, and marking returned items.
- **Phase 13 — Messaging:** item-linked conversations, inbox, read state, and message notifications; participants can individually opt in to admin review of a conversation.
- **Phase 14 — Notifications:** per-user history, unread counters, mark-read actions, and match/claim/message/recovery/admin status updates.
- **Phase 15 — Map:** Leaflet map with OpenStreetMap attribution, explicit one-shot high-accuracy browser location capture, draggable/manual pin placement, visible device accuracy radius, and broad public markers by default. Lost-report owners can explicitly opt in to show the exact pin publicly.
- **Phase 16 — Admin:** role-protected dashboard, users, reports, claims, matches, consent-enabled chats, categories, and admin activity log. Admin views of private messages are logged. Set `ADMIN_EMAIL` in Render to the email of your registered account; that account receives admin access after login. You can also persist its admin role with `python -m flask --app run.py promote-admin` from Render Shell, which uses `ADMIN_EMAIL` when set. The admin uses the normal account password; never store it in Render environment variables.
- **Phase 17 — Moderation:** users can report listings; admins can dismiss, warn, hide, delete, suspend, or resolve, with decisions logged.
- **Phase 18 — QR recovery:** revocable random-token QR links, a public safe contact form, and private recovery notes for the owner.
- **Phase 19 — Image similarity:** an average-hash image comparison contributes to the existing rule-based match score when both reports have photos.

## Notes

Email-based password recovery and profile photo uploads are not configured; those need an email transport and a secure upload workflow. The map uses Leaflet 1.9.4 and OpenStreetMap tiles with visible attribution; review the [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/) before deploying at scale.

Private conversations are hidden from administrators unless at least one participant explicitly allows admin review for that conversation. The other participant is notified when consent changes, and every admin view of message history is recorded in the system audit log. Either participant can revoke their own permission at any time; review access ends once neither participant allows it.
