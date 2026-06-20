export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// The seven reviewer-entered application values sent alongside the label image.
export type ApplicationValuePayload = {
  brand_name?: string;
  beverage_class?: "spirits" | "wine" | "malt";
  class_type_designation?: string;
  alcohol_content?: string;
  net_contents?: string;
  name_address?: string;
  country_of_origin?: string;
  malt_added_nonbeverage_alcohol?: boolean;
  malt_color_additive_applicable?: boolean;
};

export type BatchRowPayload = ApplicationValuePayload & { filename: string };

export async function getConfig() {
  const response = await fetch("/api/config");
  if (!response.ok) {
    throw await buildApiError(response, "We could not load the upload settings.");
  }
  return response.json() as Promise<unknown>;
}

function appendValues(formData: FormData, values: ApplicationValuePayload) {
  for (const [key, value] of Object.entries(values)) {
    if (typeof value === "string" && value.trim().length > 0) {
      formData.append(key, value);
    } else if (typeof value === "boolean") {
      formData.append(key, value ? "true" : "false");
    }
  }
}

export async function verifyRow(file: File, values: ApplicationValuePayload = {}) {
  const formData = new FormData();
  formData.append("file", file);
  appendValues(formData, values);

  const response = await fetch("/api/verify", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await buildApiError(response, "The review service could not process this label.");
  }

  return response.json() as Promise<unknown>;
}

export async function submitBatch(files: File[], rows: BatchRowPayload[]) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("rows", JSON.stringify(rows));

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
