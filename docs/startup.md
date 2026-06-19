# Local Startup Guide

This guide runs the Alcohol Label Verification app locally without an OpenRouter API key. The app still needs a local OpenAI-compatible vision model endpoint for real verification.

## What Runs Locally

- FastAPI backend and React frontend run in the app Docker container.
- A separate local vision model server provides the LLM endpoint.
- The browser calls only the FastAPI backend.
- The backend calls the local model server through `LOCAL_MODEL_BASE_URL`.

## Requirements

- Docker Desktop
- Git
- A local OpenAI-compatible vision model server
- Enough RAM/VRAM for the selected vision model

For practical batch uploads, use a machine with an NVIDIA GPU. CPU-only local vision inference may work for tiny tests, but it will be slow for real batches.

## 1. Clone And Enter The Repo

```powershell
git clone <repo-url>
cd Alcohol-Label-Verification-App
```

If the repo is already cloned:

```powershell
cd C:\Users\Blaise\Documents\GitHub\Alcohol-Label-Verification-App
```

## 2. Start A Local Vision Model Server

Use a server that exposes an OpenAI-compatible `/v1/chat/completions` endpoint and supports image input.

Recommended model:

```text
Qwen/Qwen2.5-VL-7B-Instruct
```

The app default model name is:

```text
qwen2.5-vl-7b-instruct
```

The easiest tested local option is Ollama:

1. Install Ollama.
2. Pull the Qwen vision model:

```powershell
ollama pull qwen2.5vl:latest
```

3. Create an app-specific alias with a larger context window:

```powershell
$modelfile = Join-Path $env:TEMP 'alv-qwen2.5vl.Modelfile'
@'
FROM qwen2.5vl:latest
PARAMETER num_ctx 16384
'@ | Set-Content -LiteralPath $modelfile -Encoding ASCII
ollama create qwen2.5vl-alv:latest -f $modelfile
Remove-Item -LiteralPath $modelfile -Force
```

The larger context window matters because full-page label/application images plus the verification prompt can exceed Ollama's default context size.

Alternative local option: LM Studio.

1. Install LM Studio.
2. Download a Qwen 2.5 VL instruct model that your machine can run.
3. Start LM Studio's local server.
4. Confirm the server exposes an OpenAI-compatible chat completions endpoint.

Common local server URLs:

```text
http://localhost:1234/v1/chat/completions
http://127.0.0.1:1234/v1/chat/completions
http://localhost:11434/v1/chat/completions
```

When the app runs inside Docker and the model server runs on the Windows host, use:

```text
http://host.docker.internal:11434/v1/chat/completions
```

## 3. Configure Local Mode

Create a `.env` file in the repo root:

```env
PROVIDER_MODE=local
LOCAL_MODEL_BASE_URL=http://host.docker.internal:11434/v1/chat/completions
LOCAL_MODEL_NAME=qwen2.5vl-alv:latest
PROVIDER_TIMEOUT_SECONDS=240
BATCH_CONCURRENCY=1
```

For a GPU-backed local model server, you can raise concurrency after a successful small test:

```env
BATCH_CONCURRENCY=2
```

Do not start high. Increase only after watching memory use and latency.

## 4. Build And Start The App

```powershell
docker compose up --build
```

Open:

```text
http://localhost:8000
```

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/api/health | ConvertTo-Json -Compress
```

Config check:

```powershell
Invoke-RestMethod http://localhost:8000/api/config | ConvertTo-Json -Compress
```

Expected config includes:

```json
{"provider_mode":"local"}
```

## 5. Try A Small Upload First

Before testing a large batch:

1. Upload one PNG or JPG containing both the application and label artwork.
2. Confirm the result completes.
3. Check the app logs if the result is a processing error.

Logs:

```powershell
docker compose logs app --tail=120
```

## 6. Run Batch Upload

Start with a small batch:

```text
5-10 files
```

Then increase gradually.

Batch behavior is controlled by:

```env
MAX_BATCH_COUNT=400
BATCH_CONCURRENCY=1
```

`MAX_BATCH_COUNT` controls how many files the app accepts in one batch.

`BATCH_CONCURRENCY` controls how many model calls run at the same time. For local models, this is the setting most likely to overload the machine.

Suggested values:

```text
CPU-only: 1
Small GPU: 1-2
Large GPU: 2-5
```

## 7. Stop The App

```powershell
docker compose down
```

Stop the local model server separately in LM Studio or whichever model runtime you are using.

## Troubleshooting

### The App Cannot Reach The Model

Use `host.docker.internal` instead of `localhost` in `.env`:

```env
LOCAL_MODEL_BASE_URL=http://host.docker.internal:1234/v1/chat/completions
```

Inside the app container, `localhost` means the app container itself, not the Windows host.

### Batch Items Fail With Processing Errors

Reduce concurrency:

```env
BATCH_CONCURRENCY=1
```

Increase timeout:

```env
PROVIDER_TIMEOUT_SECONDS=180
```

Restart:

```powershell
docker compose down
docker compose up --build
```

### The Model Rejects Images

The selected model server must support vision inputs through OpenAI-compatible message content. Text-only local models will not work for label verification.

## Current Local-Mode Limits

- No API key is required.
- A local model server is required.
- PNG/JPG are the reliable local input types.
- Batch upload works through the app, but throughput depends on local hardware and `BATCH_CONCURRENCY`.
