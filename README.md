# Alcohol Label Verification App

Prototype scaffold for an AI-powered alcohol label verification app.

## Stack

- Backend: FastAPI
- Frontend: React + TypeScript + Vite
- Runtime: single Docker container
- Deployment target: Azure App Service for Linux

## Local Docker Run

No `.env` file is required for the basic local demo.

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

## Azure Demo Deployment

See [docs/azure-app-service.md](docs/azure-app-service.md) for the Azure App Service setup and GitHub Actions deployment flow.

## Assumptions

See [docs/assumptions.md](docs/assumptions.md) for the rollout assumptions.

Key assumptions:

- Preferred demo path is online hosting through Azure App Service.
- The same app must be easy to run locally if Treasury network policy or cloud access blocks the hosted demo.
- The frontend never calls OpenRouter, local model servers, or any model provider directly.
- The frontend only calls the FastAPI backend.
- OpenRouter is the cloud default, but local mode should be able to run without an OpenRouter key when configured for a free/open-source local model backend.
- `.env` is required only when enabling OpenRouter or other real credentials.

## Storage Posture

The current scaffold is stateless. It does not store uploaded label artwork or application data on the server or in cloud storage. Future recent-history behavior should be browser-local unless server-side retention is explicitly added.

## Future Production Improvements

- Consider direct COLA imports or structured metadata ingestion in addition to the current single combined application+label upload. This is not in scope for the prototype, but it may be useful if the app is productionalized.
