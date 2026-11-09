# RentEase: a three-tier property rental web app

RentEase is a property rental listing platform (Pakistan-focused). Owners list houses, flats, portions and rooms. Tenants search them and send inquiries. Admins approve listings before they go live.

It is built as a classic **three-tier application** whose tiers can be containerised and deployed independently. That makes it a good base for the Cloud Computing (SE-490) CEA.

```
 Browser
   │  HTTPS
   ▼
┌──────────────────────────┐   Web tier (public subnet / behind load balancer)
│  frontend/  static site  │   Plain HTML + CSS + JS, served by Nginx/Apache.
│  Nginx proxies /api ───┐ │   No build step needed.
└────────────────────────┼─┘
                         ▼
┌──────────────────────────┐   Application tier (private subnet)
│  backend/  Flask REST API│   Python 3.12+, Flask, gunicorn, JWT auth.
│  port 5000               │   Stateless → can run many copies behind a LB.
└────────────┬─────────────┘
             ▼  TCP 5432 (TLS with DB_SSLMODE=require)
┌──────────────────────────┐   Database tier (private subnet)
│  PostgreSQL              │   e.g. Amazon RDS for PostgreSQL.
└──────────────────────────┘
             (optional) Amazon S3 for uploaded photos
```

## Features

| Role | Can do |
|---|---|
| Visitor | Browse approved listings; search by keyword; filter by city, type, rent range, bedrooms and furnished; sort; paginate; view details and photo gallery |
| Tenant | Everything above, plus see owner phone numbers, send inquiries, read owner replies, close inquiries |
| Owner | Create, edit and delete listings; upload and remove photos (JPG/PNG/WebP); see status (pending/approved/rejected, with the reason); reply to tenant inquiries |
| Admin | Dashboard stats; approve or reject listings (with a reason); delete listings; enable or disable user accounts |

Edited listings automatically go back to the review queue.

## Project structure

```
rentease/
├── frontend/                  ← WEB TIER (static files)
│   ├── index.html             browse + search
│   ├── property.html          listing details + inquiry form
│   ├── login.html, register.html
│   ├── dashboard.html         owner listings & inquiries / tenant inquiries
│   ├── admin.html             moderation & users
│   └── assets/
│       ├── css/styles.css
│       └── js/config.js       ← API_BASE setting (see below)
│           common.js, home.js, property.js, auth.js, dashboard.js, inquiries.js, admin.js
│
└── backend/                   ← APPLICATION TIER
    ├── wsgi.py                entry point (gunicorn wsgi:app)
    ├── manage.py              init-db / seed / create-admin commands
    ├── requirements.txt
    ├── .env.example           all configuration variables
    ├── app/
    │   ├── __init__.py        app factory, JSON logging, CORS, security headers
    │   ├── config.py          env-var configuration (+ *_FILE secrets support)
    │   ├── db.py              PostgreSQL pool (psycopg2) / SQLite for dev & tests
    │   ├── auth.py            JWT + password hashing, role checks
    │   ├── storage.py         image storage: local disk or Amazon S3
    │   ├── bootstrap.py       first-admin creation + demo seed data
    │   └── routes/            health, auth, properties, inquiries, admin
    ├── db/
    │   ├── schema.postgres.sql  ← DATABASE TIER schema
    │   └── schema.sqlite.sql
    └── tests/test_api.py      pytest suite (run in CI)
```

## Running it locally

You need **Python 3.10+** and **PostgreSQL** (any recent version, 13+). Any static file server works for the frontend; Python's built-in one is fine.

### 1. Database tier

Create a database and user, for example in `psql`:

```sql
CREATE USER rentease WITH PASSWORD 'change-me';
CREATE DATABASE rentease OWNER rentease;
```

### 2. Application tier

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit DB_PASSWORD, JWT_SECRET, ADMIN_* values
python manage.py init-db      # creates the tables
python manage.py seed         # optional: demo users + 14 listings + inquiries
python wsgi.py                # API on http://localhost:5000
```

Check that it works by opening http://localhost:5000/api/health. You should see `"database": "ok"`.

> **No PostgreSQL yet?** For a quick look, comment out the `DB_HOST` lines in `.env`. The API then falls back to a local SQLite file. Use PostgreSQL for the real deployment, because `APP_ENV=production` refuses to start on SQLite.

### 3. Web tier

For local testing without Nginx, point the frontend at the API. In `frontend/assets/js/config.js`, temporarily set:

```js
API_BASE: "http://localhost:5000/api",
```

Make sure `.env` has `CORS_ORIGINS=http://localhost:8080`, then:

```bash
cd frontend
python -m http.server 8080    # open http://localhost:8080
```

**Before deploying, change `API_BASE` back to `"/api"`.** In production, the web server reverse-proxies `/api` to the app tier, so the browser only ever talks to the web tier.

### Demo accounts (after `python manage.py seed`)

All demo accounts use the password `Password123!`. The login page has one-click buttons for them.

| Role | Email |
|---|---|
| Owner | ahmed.owner@rentease.pk (also sana.owner@, bilal.owner@) |
| Tenant | ayesha.tenant@rentease.pk (also usman.tenant@) |
| Admin | admin@rentease.pk |

Don't seed demo accounts in a public deployment unless you change these passwords. Use `ADMIN_EMAIL` / `ADMIN_PASSWORD` (read from a secret) to create the real admin instead.

### Running the tests

```bash
cd backend
pip install pytest
python -m pytest -q        # 7 tests, uses a temporary SQLite DB, no server needed
```

## Configuration

All settings are environment variables (see `backend/.env.example`). Nothing secret is hard-coded. Any variable can also be read from a file by setting `NAME_FILE=/path`, which works with Docker secrets, Kubernetes secrets, or values pulled from AWS Secrets Manager / SSM.

| Variable | Purpose | Default |
|---|---|---|
| `APP_ENV` | `production` enforces a strong JWT secret and PostgreSQL | `development` |
| `DATABASE_URL` *or* `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | PostgreSQL connection | SQLite fallback |
| `DB_SSLMODE` | `require` encrypts app→DB traffic (recommended on RDS) | unset |
| `DB_POOL_MAX` | connections per worker process | `10` |
| `AUTO_MIGRATE` | create tables on startup (safe with many instances, using an advisory lock) | `true` |
| `JWT_SECRET` | token signing key, **≥ 32 random chars in production** | dev value |
| `JWT_EXPIRES_HOURS` | login session length | `24` |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME` | first admin, created on startup if missing | unset |
| `CORS_ORIGINS` | comma-separated allowed origins (only needed without a reverse proxy) | none |
| `STORAGE_BACKEND` | `local` or `s3` | `local` |
| `UPLOAD_DIR` | folder for `local` storage | `uploads` |
| `S3_BUCKET`, `S3_PREFIX`, `AWS_REGION` | S3 storage settings (credentials come from the instance's IAM role) | — |
| `S3_PUBLIC_BASE_URL` | CloudFront URL for images; if unset, short-lived pre-signed URLs are used | — |
| `MAX_IMAGE_MB`, `MAX_IMAGES_PER_PROPERTY` | upload limits | `5`, `8` |
| `INSTANCE_ID` | name shown in the `X-Served-By` header and page footer | hostname |
| `LOG_LEVEL` | logging level | `INFO` |

## Built-in support for the cloud deployment

The app was written with the CEA requirements in mind. These are the hooks you will use:

- **Health checks:** `GET /api/health` returns 200 only when the database is reachable (503 otherwise). Use it as the load balancer target group health check. `GET /api/health/live` checks only that the process is up (useful for a Kubernetes liveness probe).
- **Stateless app tier:** JWT auth means no server-side sessions. Any instance can serve any request, so Auto Scaling / multiple replicas work without sticky sessions.
- **Load balancing is visible:** every API response carries an `X-Served-By` header, and the page footer shows "Served by app instance: …". Refresh the page to watch the load balancer switch instances, which makes a good screenshot.
- **Shared image storage:** with `STORAGE_BACKEND=s3`, photos go to a private, encrypted S3 bucket. That way every instance sees the same images. Local disk only works with a single instance or a shared volume (EFS). This covers the CEA's "object storage" enhancement.
- **Secrets:** read from env vars or `*_FILE`, never from code. Production mode refuses to start with a weak or default JWT secret.
- **Encrypted DB connection:** set `DB_SSLMODE=require`.
- **Centralised logging:** logs are JSON lines on stdout (request id, method, path, status, duration, user, instance). The CloudWatch agent / awslogs driver, Loki or ELK can ingest them directly. Health-check calls are excluded to cut noise.
- **Safe migrations:** the schema is idempotent (`CREATE TABLE IF NOT EXISTS`) and guarded by a PostgreSQL advisory lock, so several instances starting at once don't collide.
- **Production server:** run the API with `gunicorn --workers 3 --bind 0.0.0.0:5000 wsgi:app`, not `python wsgi.py`.
- **Web tier → app tier:** the frontend calls relative `/api/...` URLs. The web tier's Nginx should `proxy_pass` `/api/` to the app tier's private address (or an internal load balancer). The app tier then needs no public exposure.
- **Upload size:** set Nginx `client_max_body_size` to at least `45m` (8 photos × 5 MB + overhead) so photo uploads aren't rejected by the proxy.

## API reference (all under `/api`)

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/health`, `/health/live` | anyone | health checks |
| POST | `/auth/register` | anyone | `{name, email, password, role: owner\|tenant, phone?}` → `{token, user}` |
| POST | `/auth/login` | anyone | `{email, password}` → `{token, user}` |
| GET / PUT | `/auth/me` | signed in | get / update own name and phone |
| GET | `/properties` | anyone | approved listings; query: `q, city, area, type, min_rent, max_rent, bedrooms, furnished, sort (newest\|rent_asc\|rent_desc), page, page_size` |
| GET | `/meta/filters` | anyone | cities with live listings, property types |
| GET | `/properties/{id}` | anyone | details; owner phone only when signed in |
| POST | `/properties` | owner | create (starts as `pending`) |
| PUT / DELETE | `/properties/{id}` | owner, admin | edit (back to `pending`) / delete |
| GET | `/my/properties` | owner | own listings with status and inquiry counts |
| POST | `/properties/{id}/images` | owner | multipart field `images` (one or more files) |
| DELETE | `/images/{id}` | owner, admin | remove a photo |
| POST | `/properties/{id}/inquiries` | tenant | `{message, contact_phone?}` |
| GET | `/my/inquiries` | owner, tenant | received (owner) or sent (tenant) |
| PATCH | `/inquiries/{id}` | owner, tenant | owner: `{reply}` or `{status: "closed"}`; tenant: `{status: "closed"}` |
| GET | `/admin/stats` | admin | counts |
| GET | `/admin/properties?status=pending\|approved\|rejected\|all` | admin | moderation queue |
| PATCH | `/admin/properties/{id}` | admin | `{status: approved\|rejected, reason}` |
| GET | `/admin/users` | admin | all users |
| PATCH | `/admin/users/{id}` | admin | `{is_active: true\|false}` |

Authenticated requests send `Authorization: Bearer <token>`. Errors come back as `{"error": "...", "details": {field: message}}`.

## Database schema

Four tables: `users`, `properties`, `property_images`, `inquiries` (see `backend/db/schema.postgres.sql`).

- **Foreign keys** cascade on delete.
- **CHECK constraints** cover roles, statuses, property types and positive rent.
- **Indexes** support the search query (`status, city, rent`) and the owner and tenant lookups.

## Security notes

- Passwords are hashed with Werkzeug (scrypt).
- Admins can't self-register.
- Role checks run on every protected endpoint, and owners can only touch their own listings.
- All SQL is parameterised.
- Uploaded images are checked by their file signature (not by file extension), size-limited and stored under random names.
- The frontend escapes all user content before rendering.
- `X-Content-Type-Options: nosniff` is set on API responses.
- Login redirects only allow same-site paths.

## Running with Docker (all three tiers)

You need Docker Desktop. If they are still running, stop the local `python wsgi.py` and `http.server` first, because port 8080 is needed.

```bash
copy .env.example .env          # macOS/Linux: cp .env.example .env  — then edit the values
docker compose up --build -d    # builds both images and starts db, backend, frontend
docker compose ps               # all three should become "healthy"
docker compose exec backend python manage.py seed   # optional demo data
```

Open http://localhost:8080. Useful commands:

| Command | What it does |
|---|---|
| `docker compose logs -f backend` | follow the API's JSON logs |
| `docker compose up --build -d` | rebuild after code changes |
| `docker compose down` | stop (data is kept in volumes) |
| `docker compose down -v` | stop **and delete** the database and uploads |

| File | Purpose |
|---|---|
| `backend/Dockerfile` | Python 3.12 slim, gunicorn, non-root user, health check |
| `frontend/Dockerfile` | Nginx serving the site; forces `API_BASE="/api"` inside the image |
| `frontend/nginx.conf.template` | proxies `/api/` to `BACKEND_URL`; security headers; `/healthz`; 45 MB upload limit |
| `docker-compose.yml` | db + backend + frontend on two networks; only port 8080 is published |

The frontend image reads two environment variables at start-up:
- **`BACKEND_URL`** is where `/api` is forwarded: `http://backend:5000` in Compose, or the app tier's private IP / internal load balancer on AWS.
- **`NGINX_RESOLVER`** is the DNS server: `127.0.0.11` in Docker, `169.254.169.253` inside an AWS VPC.
