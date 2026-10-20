# SecureHire AI — Quick Start (Docker / Windows PowerShell)

## 1. Configure optional Gemini AI
Open the root `.env` file and set `GEMINI_API_KEY` to your own Google AI Studio API key.
The key is optional for startup: the ML fraud analysis still runs without it, while
Gemini company research is marked unavailable and the career assistant uses its
built-in grounded fallback until a key is configured.

Never commit `.env` or share it. If a key was ever shared, revoke it and create a new one.

## 2. Start the complete application
From the `securehire-ai\docker` folder:

```powershell
docker compose down
docker compose up -d --build
docker compose ps
```

All four services should become `healthy`.

## 3. Open the app
Frontend: http://localhost:3000
Backend docs: http://localhost:8000/docs
Backend health: http://localhost:8000/health

## 4. Create your account
Use **Create account** in the frontend. The app creates the user and logs you in automatically.

This is important: a fresh PostgreSQL volume has zero users, so trying to log in before registering will correctly return `Incorrect email or password`.

## 5. Verify authentication from PowerShell (optional)
Use PowerShell's native HTTP client to avoid Windows `curl` quoting issues:

```powershell
$body = @{
  email = "test@example.com"
  password = "123456789"
  full_name = "Test User"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/auth/register" `
  -ContentType "application/json" `
  -Body $body
```

Then verify the user exists:

```powershell
docker compose exec backend python -c "from app.db.session import SessionLocal; from app.models.models import User; db=SessionLocal(); print([(u.email, u.role, u.is_active) for u in db.query(User).all()]); db.close()"
```

## 6. Verify Gemini
After setting the key:

```powershell
docker compose exec backend python -c "from google import genai; import os; c=genai.Client(api_key=os.environ['GEMINI_API_KEY']); r=c.models.generate_content(model=os.environ['GEMINI_MODEL'], contents='Reply with exactly: Gemini connection works'); print(r.text)"
```

## 7. Verify the real analysis endpoint
The `/jobs/analyze` endpoint is protected. First register/login in the UI; then use the Analyze Job page.

## Important fixes included
- Docker frontend healthcheck uses `curl`, which is present in the nginx image used here.
- Local Docker backend mounts the repository's `models/` and `data/` directories, so ML artifacts and demo seed data are available inside the container.
- `MODELS_ROOT=/models` and `DATA_ROOT=/data` are explicit.
- Compose syntax is valid; `docker compose config` should succeed.
- Authentication remains JWT-based and protected endpoints require a Bearer token.
- `.env` files in this package contain placeholders instead of the previously exposed Gemini key.
