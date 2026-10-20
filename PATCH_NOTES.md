# SecureHire AI — reliability patch notes

This package includes the full application and the following fixes:

- Keeps the existing ML fraud-risk model as the core job-analysis engine; a Gemini key is not required for the model prediction.
- Improves expired-session recovery: a rejected token is cleared and the user is redirected to sign in again with an explanatory message.
- Adds company-name web search when no company website is supplied, then attempts to retrieve readable public pages. Retrieved URLs are checked by the existing public-host/redirect safety guard before fetching.
- When `GEMINI_API_KEY` is absent, company research returns a clearly labelled source preview instead of an empty dead-end error. It does not claim that an AI verification happened.
- With a valid `GEMINI_API_KEY`, the existing Gemini-backed research flow summarizes the retrieved public pages and displays source links.
- Preserves the existing navy/blue UI, model artifacts, datasets, pipeline code, Docker services, and application pages.

## Run

From this folder in PowerShell:

```powershell
docker compose -f .\docker\docker-compose.yml config --quiet
docker compose -f .\docker\docker-compose.yml up -d --build
docker compose -f .\docker\docker-compose.yml ps
```

Open `http://localhost:3000`.

If the app still shows `Could not validate credentials`, log out and log back in. If that does not clear it, clear site data for `localhost:3000` and reload, then sign in. This commonly happens when a browser token was created under a previous local `SECRET_KEY`.

To enable AI-generated company research and AI chat, add a valid `GEMINI_API_KEY` to the root `.env` file and rebuild the backend:

```powershell
docker compose -f .\docker\docker-compose.yml up -d --build backend
```

Company-name search and public-page retrieval may depend on your network allowing DuckDuckGo HTML search and the target websites. Without a Gemini key, the app shows a source preview, not an AI-generated assessment.
