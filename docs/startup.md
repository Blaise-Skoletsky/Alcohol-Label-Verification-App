# Startup Guide

This guide has two decisions:

1. Choose a model provider path:
   - [OpenRouter](#path-a-openrouter-provider) if you have an OpenRouter API key.
   - [Local Ollama](#path-b-local-ollama-provider) if you want to run without an
     API key.
2. Choose an app startup path:
   - [Docker startup](#path-1-docker-startup) for the simplest app run.
   - [Individual startup](#path-2-individual-backend-and-frontend-startup) when
     you want separate backend and frontend dev servers.

The browser always calls the FastAPI backend. The frontend never calls
OpenRouter, Ollama, or any model provider directly.

## Requirements

- Git
- Docker Desktop, if using the Docker startup path
- Python 3.12, if using the individual backend startup path
- Node.js 22, if using the individual frontend startup path
- An OpenRouter API key for the OpenRouter provider path, or Ollama for the local
  provider path

Clone and enter the repo:

```powershell
git clone YOUR_REPO_URL
cd Alcohol-Label-Verification-App
```

If the repo is already cloned:

```powershell
cd C:\Users\Blaise\Documents\GitHub\Alcohol-Label-Verification-App
```

Do not commit your `.env` file.

Create your local `.env` from the checked-in example:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` for either the OpenRouter path or the local Ollama path below.

## Path A: OpenRouter Provider (What deployed URL uses)

Use this path when you have an OpenRouter API key and want the backend to call
OpenRouter. Openrouter uses powerful models that are able to pass the <5 second criteria. 

In `.env`, set the provider to OpenRouter and add your OpenRouter API key:

```env
PROVIDER_MODE=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL_PRIMARY=google/gemini-3.1-flash-lite-preview
OPENROUTER_MODEL_FALLBACKS=google/gemini-2.5-flash-lite,google/gemini-2.5-flash
OPENROUTER_TIMEOUT_SECONDS=45
```

Notes:
- The selected models are not free, the openrouter API key will need credits loaded to run.
- `OPENROUTER_API_KEY` is required for this path.
- The model variables are optional, but setting them makes the selected model
  order explicit.
- `OPENROUTER_TIMEOUT_SECONDS` is the timeout variable currently passed by
  `docker-compose.yml`.

For individual backend startup, `PROVIDER_TIMEOUT_SECONDS=45` also works because
the backend reads the `.env` file directly.

## Path B: Local Ollama Provider

Use this path when you want to run without an OpenRouter API key. The app still
needs a local OpenAI-compatible vision model endpoint. Processing time is much slower than with openrouter. Not recommended for any cloud deployments.

### 1. Install Ollama

Official downloads:

- Windows: <https://ollama.com/download/windows>
- macOS: <https://ollama.com/download/mac>
- Linux: <https://ollama.com/download/linux>

Windows PowerShell install command from Ollama:

```powershell
irm https://ollama.com/install.ps1 | iex
```

Linux install command from Ollama:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

After installation, confirm Ollama is available:

```powershell
ollama --version
```

### 2. Pull A Vision Model

Recommended local model:

```text
Qwen/Qwen2.5-VL-7B-Instruct
```

Pull it with Ollama:

```powershell
ollama pull qwen2.5vl:latest
```

Create an app-specific alias with a larger context window:

```powershell
$modelfile = Join-Path $env:TEMP 'alv-qwen2.5vl.Modelfile'
@'
FROM qwen2.5vl:latest
PARAMETER num_ctx 16384
'@ | Set-Content -LiteralPath $modelfile -Encoding ASCII
ollama create qwen2.5vl-alv:latest -f $modelfile
Remove-Item -LiteralPath $modelfile -Force
```

The larger context window matters because label artwork plus structured
application data and the verification prompt can exceed Ollama's default context
size.

Confirm the model exists:

```powershell
ollama list
```

### 3. Configure Local Provider Mode

For Docker startup, keep these values in `.env`:

```env
PROVIDER_MODE=local
LOCAL_MODEL_BASE_URL=http://host.docker.internal:11434/v1/chat/completions
LOCAL_MODEL_NAME=qwen2.5vl-alv:latest
OPENROUTER_TIMEOUT_SECONDS=240
```

For individual backend startup, change the model URL in `.env` to `localhost`:

```env
PROVIDER_MODE=local
LOCAL_MODEL_BASE_URL=http://localhost:11434/v1/chat/completions
LOCAL_MODEL_NAME=qwen2.5vl-alv:latest
PROVIDER_TIMEOUT_SECONDS=240
```

For local models, start with low concurrency. CPU-only local vision inference may
work for tiny tests, but it will be slow for real batches. A GPU-backed machine
is strongly preferred for practical batch uploads.

## Path 1: Docker Startup (Preferred)

Use this path after choosing either the OpenRouter `.env` or the local Ollama
`.env` above. Docker starts the FastAPI backend and serves the built React
frontend from the same app container.

For the local Ollama provider path, Ollama runs separately on your host machine.
The Docker app container reaches it through `host.docker.internal`.

Start the app:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:8000
```

Stop the app:

```powershell
docker compose down
```

Stop Ollama separately if you started it for the local provider path.

## Path 2: Individual Backend And Frontend Startup

Use this path when you want the backend and frontend running as separate dev
servers. The frontend dev server proxies `/api` requests to
`http://localhost:8000`.

### 1. Start The Backend

Run these commands from the repo root:

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .\backend
python -m uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

Leave that terminal running.

Backend health check:

```powershell
Invoke-RestMethod http://localhost:8000/api/health | ConvertTo-Json -Compress
```

### 2. Start The Frontend

Open a second terminal in the repo route:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```


### The Model Rejects Images

The selected local model server must support vision inputs through
OpenAI-compatible message content. Text-only local models will not work for label
verification.
