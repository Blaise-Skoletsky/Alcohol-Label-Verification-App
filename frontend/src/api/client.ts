export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function getConfig() {
  const response = await fetch("/api/config");
  if (!response.ok) {
    throw await buildApiError(response, "We could not load the upload settings.");
  }
  return response.json() as Promise<unknown>;
}

export async function verifySingle(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/verify", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await buildApiError(response, "The review service could not process this file.");
  }

  return response.json() as Promise<unknown>;
}

export async function submitBatch(files: File[]) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const response = await fetch("/api/batches", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await buildApiError(response, "The review service did not accept the selected batch.");
  }

  return response.json() as Promise<unknown>;
}

export async function getBatch(batchId: string) {
  const response = await fetch(`/api/batches/${encodeURIComponent(batchId)}`);
  if (!response.ok) {
    throw await buildApiError(response, "We could not load the latest batch status.");
  }
  return response.json() as Promise<unknown>;
}

async function buildApiError(response: Response, fallbackMessage: string) {
  let message = fallbackMessage;
  try {
    const body = (await response.json()) as unknown;
    if (isRecord(body)) {
      const detail = body.detail;
      if (typeof detail === "string" && detail.trim().length > 0) {
        message = detail;
      } else if (isRecord(detail) && typeof detail.message === "string") {
        message = detail.message;
      }
    }
  } catch {
    // Keep the fallback message when the server response is not JSON.
  }
  return new ApiError(message, response.status);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
