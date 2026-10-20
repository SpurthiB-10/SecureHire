# Deploying SecureHire AI to ONE public URL

This gets you a single link — open it and you see the full app (landing page,
analyze job, dashboard, everything) at the same origin. No separate frontend/
backend links, no juggling multiple services in the browser.

**How it works:** the React frontend is built into static files and served
directly by the FastAPI backend (`backend/app/main.py`), so there's exactly
one running service. `docker/Dockerfile.deploy` builds the frontend, trains
the ML model, and bakes everything into one image. You only need to bring a
PostgreSQL database — Redis is intentionally left out of production (the app
degrades gracefully without it; see "Why no Redis" below).

**Cost: $0.** Two free-tier signups, no credit card required for either.

---

## Step 1 — Push this repo to GitHub

```bash
cd securehire-ai
git init
git add .
git commit -m "SecureHire AI"
gh repo create securehire-ai --public --source=. --push
# (or push manually to a repo you create on github.com)
```

## Step 2 — Create a free, permanent PostgreSQL database on Neon

Neon's free tier doesn't expire (unlike Render's built-in free Postgres, which
deletes itself after 30 days) — that's why we use it here.

1. Go to **neon.tech** → sign up (GitHub login works, no card needed).
2. Create a new project → note the **connection string** it gives you, e.g.:
   ```
   postgresql://neondb_owner:AbCdEf123@ep-cool-name-12345.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
3. Keep this tab open — you'll paste this string in Step 4.

*(You don't need to run `schema.sql` manually — the backend creates all
tables automatically on first boot.)*

## Step 3 — Deploy to Render

1. Go to **render.com** → sign up (GitHub login works, no card needed).
2. Click **New → Blueprint**.
3. Connect your GitHub account and select the `securehire-ai` repo.
4. Render detects `render.yaml` at the repo root automatically and shows
   one service: `securehire-ai` (Docker runtime, free plan).
5. Click **Apply** — Render will ask you to fill in the `DATABASE_URL`
   value (it's marked `sync: false` in the blueprint, meaning you supply it).
   Paste the Neon connection string from Step 2.
6. Click **Deploy**.

## Step 4 — Wait for the build (first deploy takes ~5–8 minutes)

The build log will show, in order:
- npm install + `vite build` (frontend)
- synthetic dataset generation + ETL pipeline (data engineering)
- model training — Logistic Regression / Random Forest / XGBoost / Ensemble (ML)
- backend dependency install
- container boot, table creation, demo-data auto-seeding

When it's done, Render shows your live URL, something like:
```
https://securehire-ai.onrender.com
```

**That's it — open that one link.** You'll see the landing page, and every
feature (Analyze Job, Trusted Feed, Dashboard, Admin) lives at that same
domain (e.g. `/analyze`, `/dashboard`).

---

## Important things to know about the free tier

- **Cold starts:** Render's free web services sleep after 15 minutes of no
  traffic. The next visit takes ~30–60 seconds to wake up — this is normal,
  not a bug. (Worth mentioning if you're sharing the link with a recruiter:
  "give it a minute on the first load.")
- **The dashboard/feed won't be empty on first visit** — the backend
  auto-seeds ~40 real model predictions on its very first boot
  (`app/services/seed_service.py`), so charts and the Trusted Jobs Feed have
  data immediately.
- **Why no Redis:** free managed Redis isn't reliably free across providers
  in 2026, and the app already treats Redis purely as an optional
  performance cache — `backend/app/services/cache.py` fails open (falls back
  to computing predictions fresh) if Redis is unreachable. Skipping it in
  production keeps this a genuinely single-service deployment. If you want
  to add it back: create a free Upstash Redis instance and set `REDIS_URL`
  in the Render dashboard — no code changes needed.

## Updating the deployment later

Render auto-redeploys on every push to your GitHub repo's default branch —
just `git push` and it rebuilds (retraining the model fresh each time, since
training happens at build time).

## Alternative: any other Docker host

`docker/Dockerfile.deploy` is a standard multi-stage Dockerfile — it isn't
Render-specific. The same image builds and runs on Railway, Fly.io, a plain
VPS, or any host that can build from a Dockerfile and set a `DATABASE_URL`
env var + expose `$PORT`.
