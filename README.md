# ⚡ API Mockmaster

> Spin up a real, hittable fake API endpoint in **one second** — no signup, no config, no Node build step.

API Mockmaster is a self-contained SaaS for frontend engineers and QA teams who need
throwaway API endpoints *right now*: to build a UI before the backend exists, to test
loading spinners with a controllable delay, or to reproduce a `500` on demand.

Define a method, a path, a JSON body, and an optional latency — click **Generate** — and
you instantly get a URL like:

```
http://localhost:8000/mock/a1b2c3d4e5/api/v1/posts
```

…that you can paste straight into your `fetch()` calls.

---

## ✨ Features

| | |
|---|---|
| 🚀 **1-second mocks** | Method + path + JSON → live URL, copied to your clipboard automatically. |
| ⏱ **Latency simulation** | Set `delay_ms` to test loading states and timeouts (server-side `asyncio.sleep`). |
| 🎯 **Any status code** | Return `200`, `404`, `500`… to exercise every branch of your error handling. |
| 🔐 **Accounts & multi-tenancy** | Email/password auth (bcrypt + JWT). Each user only sees and controls their own mocks. |
| 🛡 **Abuse guards** | Per-user mock quota, response-size caps, and login rate limiting out of the box. |
| 🌐 **Zero-friction CORS** | `allow_origins=["*"]` — call mocks from `localhost:3000`, `:5173`, anywhere, no preflight pain. |
| 🛡 **Double JSON validation** | Broken JSON is caught in the browser *and* on the server before it's ever stored. |
| 🗄 **SQLite by default, Postgres-ready** | One env var (`DATABASE_URL`) switches the whole backend to PostgreSQL. |
| 🎨 **Vercel-grade dashboard** | Single-file dark-mode SPA served by FastAPI. No webpack, no `node_modules`. |

---

## 🏃 Quick start

```bash
# 1. clone / cd into the project
cd api-mockmaster

# 2. create a virtualenv (recommended)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. install dependencies
pip install -r requirements.txt

# 4. run it
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** — create an account, sign in, and start mocking.
Interactive API docs live at **http://localhost:8000/docs**.

> The SQLite database file `mockmaster.db` is created automatically on first boot.

### ⚠️ Set `SECRET_KEY` in production

JWT sessions are signed with `SECRET_KEY`. If it's unset, a random key is generated
per process (sessions reset on every restart). For any real deployment:

```bash
export SECRET_KEY="$(openssl rand -hex 32)"
```

All tunables (`SECRET_KEY`, `DATABASE_URL`, quotas, rate limits) are listed in
[`.env.example`](.env.example).

---

## 🔌 Using a mock from your frontend

Create a `GET /api/v1/posts` mock in the dashboard, copy the URL, and drop it in:

### React / Vue / vanilla `fetch`

```js
// The exact URL the dashboard gives you:
const MOCK_URL = "http://localhost:8000/mock/a1b2c3d4e5/api/v1/posts";

async function getPosts() {
  const res = await fetch(MOCK_URL);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

getPosts().then(console.log);
```

### React — testing a loading state with the delay feature

```jsx
import { useEffect, useState } from "react";

const MOCK_URL = "http://localhost:8000/mock/a1b2c3d4e5/api/v1/posts"; // delay_ms: 2000

export function Posts() {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch(MOCK_URL).then((r) => r.json()).then(setData);
  }, []);

  // The mock waits 2s before responding → your spinner gets real airtime.
  if (!data) return <Spinner />;
  return <PostList posts={data} />;
}
```

### POST / PUT / DELETE

The mock matches on **method**, so create one mock per method you need:

```js
await fetch("http://localhost:8000/mock/<id>/api/v1/posts", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ title: "Hello" }),
});
```

---

## 🐘 Switching to PostgreSQL

No code changes. Set one environment variable and install the driver:

```bash
pip install "psycopg[binary]"
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/mockmaster"
uvicorn app.main:app
```

The engine, sessions, and table creation all read from `DATABASE_URL` — SQLite is
just the convenient default for local/demo use.

---

## 🚢 Deployment

### Docker (any host)

```bash
export SECRET_KEY="$(openssl rand -hex 32)"
docker compose up --build      # → http://localhost:8000
```

The compose file mounts a named volume so the SQLite DB survives restarts, and
ships a commented-out PostgreSQL service you can switch on in two lines.

### Render / Railway / Fly.io (one-click style)

The image honours the platform-provided `$PORT`, so a managed deploy needs only:

1. Point the platform at this repo (it autodetects the `Dockerfile`).
2. Set env vars: `SECRET_KEY` (required) and, for durable data, `DATABASE_URL`
   to a managed Postgres instance.
3. Deploy. HTTPS and a domain are provisioned by the platform automatically.

> SQLite on ephemeral filesystems is wiped on redeploy — use Postgres (or a
> persistent disk) for anything beyond a demo.

---

## 🧱 Architecture

```
api-mockmaster/
├── app/
│   ├── main.py            # FastAPI app: auth, CORS, owner-scoped CRUD, dynamic router, abuse guards
│   ├── auth.py            # bcrypt password hashing + JWT sessions + current-user dependency
│   ├── database.py        # SQLAlchemy engine/session (SQLite ⇄ Postgres via env)
│   ├── models.py          # User + MockEndpoint ORM models (owner_id multi-tenancy)
│   ├── schemas.py         # Pydantic schemas + server-side JSON & size validation
│   └── templates/
│       └── index.html     # Single-file dark-mode dashboard SPA w/ auth gate (Tailwind CDN)
├── alembic/               # Database migrations (env.py + versions/)
│   └── versions/0001_initial.py
├── tests/                 # pytest suite (auth, tenancy, serving, abuse)
├── .github/workflows/ci.yml  # CI: migrations round-trip + tests (3.11/3.12)
├── Dockerfile             # Production image (honours $PORT)
├── docker-compose.yml     # Local/prod stack (+ optional Postgres)
├── alembic.ini
├── .env.example           # All configurable env vars
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

### Auth model

- `POST /api/auth/register` and `/api/auth/login` return a bearer JWT.
- The **management API** (`/api/mocks`) requires that token and is scoped to the
  caller — you can never see or touch another user's mocks (same `404` either way).
- The **mock-serving routes** (`/mock/...`) stay fully public and unauthenticated —
  that's the entire point: any frontend hits them freely.

### Still recommended before heavy production traffic

The product is publishable today; these harden it further as you scale:

- **Redis-backed rate limiting** — the built-in limiter is per-process. Move it to
  Redis once you run more than one worker/instance.
- **Email verification & password reset** — expected for a public consumer signup.

---

## 🧪 Tests, CI & migrations

```bash
pip install -r requirements-dev.txt

# Apply the schema (production uses this instead of auto-create):
export DATABASE_URL="sqlite:///./mockmaster.db"
alembic upgrade head

# Run the suite (25 tests: auth, multi-tenancy, serving, abuse guards):
pytest
```

- **Alembic** owns the schema. The initial migration is verified drift-free against
  the ORM models (`alembic revision --autogenerate` produces no changes). In production
  set `AUTO_CREATE_TABLES=0` so migrations are the single source of truth.
- **pytest** covers every guarantee that matters: token auth, tenant isolation
  (no cross-account access, no existence leaks), public mock serving incl. latency &
  status codes, JSON validation, per-user quota, payload caps, and login rate limiting.
- **GitHub Actions** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the
  Alembic upgrade→downgrade→upgrade round-trip and the full test suite on Python
  3.11 and 3.12 for every push and PR.

**Request flow for a mock call**
`GET /mock/{mock_id}/{path}` → look up the row by `id` + verify `method` →
`asyncio.sleep(delay_ms)` if set → return stored JSON with the configured status code.

The dynamic route is registered for `GET/POST/PUT/PATCH/DELETE`, so a single handler
serves every fake endpoint your users create.

---

## 💎 For Acquire.com buyers — why this is a clean asset

- **Tiny, legible codebase.** A handful of files, no build pipeline, no front-end
  framework lock-in. A new owner can read the entire thing in 20 minutes and ship a
  feature the same day.
- **Due-diligence ready.** 25 automated tests, GitHub Actions CI on two Python
  versions, and drift-checked Alembic migrations — the engineering hygiene a buyer's
  technical review looks for is already in place.
- **Near-zero hosting cost.** Stateless FastAPI + SQLite runs on a $5 box or a free tier;
  scales to managed Postgres by flipping one env var.
- **Monetization foundation already built:**
  - ✅ Per-user accounts and multi-tenant isolation (auth + `owner_id`) are done.
  - ✅ Per-user quota enforcement is in place — flip it into paid tiers by varying
    `MAX_MOCKS_PER_USER` per plan.
  - Remaining upsells are pure product work, not re-architecture: custom domains,
    team workspaces, request logging/analytics, billing (Stripe), CI integrations.
- **Proven, evergreen demand.** Every frontend team mocks APIs; competitors (Mockoon,
  Beeceptor, Mocky) validate the market and willingness to pay.
- **No dependency rot risk.** Three production dependencies (FastAPI, Uvicorn, SQLAlchemy),
  all actively maintained with massive communities.

The product is intentionally minimal so its **distribution and pricing**, not its
engineering, become the growth levers for an acquirer.

---

## 📄 License

MIT — do whatever grows the business.
