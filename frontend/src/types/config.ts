export type AppConfig = {
  maxUploadMb: number;
  maxBatchLabels: number;
  allowedFileTypes: string[];
  providerMode: string;
  environment: string;
  demoBatchManifestUrl: string | null;
};

export type ConfigResponse = Partial<{
  max_upload_mb: number;
  max_batch_labels: number;
  allowed_file_types: string[];
  provider_mode: string;
  environment: string;
  demo_batch_manifest_url: string | null;
}>;

export const DEFAULT_CONFIG: AppConfig = {
  maxUploadMb: 20,
  maxBatchLabels: 350,
  allowedFileTypes: [".png", ".jpg", ".jpeg"],
  providerMode: "local",
  environment: "development",
  demoBatchManifestUrl: null,
};
