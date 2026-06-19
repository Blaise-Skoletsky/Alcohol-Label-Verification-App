export type AppConfig = {
  maxUploadMb: number;
  maxBatchLabels: number;
  allowedFileTypes: string[];
  providerMode: string;
};

export type ConfigResponse = Partial<{
  max_upload_mb: number;
  max_batch_labels: number;
  allowed_file_types: string[];
  provider_mode: string;
}>;

export const DEFAULT_CONFIG: AppConfig = {
  maxUploadMb: 20,
  maxBatchLabels: 25,
  allowedFileTypes: [".png", ".jpg", ".jpeg", ".pdf"],
  providerMode: "local",
};
