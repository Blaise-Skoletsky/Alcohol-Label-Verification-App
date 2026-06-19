# Alcohol Label Verification App

Prototype scaffold for an AI-powered alcohol label verification app.

## Stack

- Backend: FastAPI
- Frontend: React + TypeScript + Vite
- Runtime: single Docker container
- Deployment target: Azure App Service for Linux

## Local Docker Run

The default provider mode is `local`. A local run needs an OpenAI-compatible vision model server unless `.env` switches `PROVIDER_MODE=openrouter`.

```powershell
docker compose up --build
```

Open:

- App: http://localhost:8000
- Health: http://localhost:8000/api/health

## Local Development

Backend:

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

## Model Provider Modes

The app defaults to `PROVIDER_MODE=local`. Use `LOCAL_MODEL_BASE_URL` and `LOCAL_MODEL_NAME` to point the backend at a real local OpenAI-compatible vision model server.

Use `PROVIDER_MODE=openrouter` with `OPENROUTER_API_KEY` to call OpenRouter from the backend. The frontend never receives provider credentials and never calls model providers directly.

## Azure Demo Deployment

See [docs/azure-app-service.md](docs/azure-app-service.md) for the Azure App Service setup and GitHub Actions deployment flow.

## Assumptions

See [docs/assumptions.md](docs/assumptions.md) for the rollout assumptions.

Key assumptions:

- Preferred demo path is online hosting through Azure App Service.
- The same app must be easy to run locally if Treasury network policy or cloud access blocks the hosted demo.
- The frontend never calls OpenRouter, local model servers, or any model provider directly.
- The frontend only calls the FastAPI backend.
- Local mode is the default runtime path. OpenRouter is the cloud/demo provider when `PROVIDER_MODE=openrouter` is configured.
- `.env` is required only when enabling OpenRouter or other real credentials.

## Storage Posture

The current scaffold is stateless. It does not store uploaded label artwork or application data on the server or in cloud storage. Future recent-history behavior should be browser-local unless server-side retention is explicitly added.

## Future Production Improvements

- Consider direct COLA imports or structured metadata ingestion in addition to the current single combined application+label upload. This is not in scope for the prototype, but it may be useful if the app is productionalized.
