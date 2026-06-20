import { useEffect, useState } from "react";
import { getConfig } from "../api/client";
import { clampNumber } from "../lib/format";
import { DEFAULT_CONFIG, type AppConfig, type ConfigResponse } from "../types/config";

export function useAppConfig() {
  const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG);
  const [configError, setConfigError] = useState("");

  useEffect(() => {
    void loadConfig();
  }, []);

  async function loadConfig() {
    try {
      const data = (await getConfig()) as ConfigResponse;
      setConfig(normalizeConfig(data));
      setConfigError("");
    } catch {
      setConfig(DEFAULT_CONFIG);
      setConfigError(
        "We could not load the upload settings, so standard limits are shown for now.",
      );
    }
  }

  return { config, configError, reloadConfig: loadConfig };
}

function normalizeConfig(data: ConfigResponse): AppConfig {
  return {
    maxUploadMb: clampNumber(data.max_upload_mb, DEFAULT_CONFIG.maxUploadMb),
    maxBatchLabels: clampNumber(data.max_batch_labels, DEFAULT_CONFIG.maxBatchLabels),
    allowedFileTypes:
      Array.isArray(data.allowed_file_types) && data.allowed_file_types.length > 0
        ? data.allowed_file_types
        : DEFAULT_CONFIG.allowedFileTypes,
    providerMode:
      typeof data.provider_mode === "string" && data.provider_mode.trim().length > 0
        ? data.provider_mode
        : DEFAULT_CONFIG.providerMode,
    environment:
      typeof data.environment === "string" && data.environment.trim().length > 0
        ? data.environment
        : DEFAULT_CONFIG.environment,
    demoBatchManifestUrl:
      typeof data.demo_batch_manifest_url === "string" &&
      data.demo_batch_manifest_url.trim().length > 0
        ? data.demo_batch_manifest_url
        : null,
  };
}
