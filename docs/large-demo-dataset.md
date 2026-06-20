# Large Demo Dataset

This note captures the intended setup for the hosted large batch demo dataset.
The goal is to let the production Azure demo load a realistic 300-label batch
without committing hundreds of image files to the Git repository.

## Goal

- Keep the Git repository lightweight.
- Keep the full 300-label interactive demo available in the hosted Azure app.
- Store the large demo images and CSV outside Git, in Azure Blob Storage.
- Show the large demo batch button only in production.
- Keep local development focused on the normal app workflow and the smaller
  tracked test/sample fixtures.

## Current Local Files

The local large-label source directory is:

```text
data/labels
```

Current local image count:

```text
400 image files
```

The generated 300-row demo CSV is:

```text
data/batch_upload_example.csv
```

Current CSV status:

```text
300 rows
45,808 bytes
```

The CSV uses this user-facing batch upload schema:

```csv
Image,Beverage Class,Brand Name,Class Type,Alcohol Content,Net Contents,Name and Address,Country of Origin,Malt Added Nonbeverage Alcohol,Malt Color Additive Applicable
```

Important: `data/` is currently gitignored. These large demo files will not be
committed unless intentionally force-added. For this workflow, do not commit the
full image dataset.

## CSV Semantics

Each row represents one label/application record.

- `Image`: filename only, not a local path.
- `Beverage Class`: `Wine`, `Spirits`, or `Malt`.
- `Brand Name`: application brand/business name.
- `Class Type`: class/type designation submitted by the application.
- `Alcohol Content`: required for spirits, conditionally required for wine and
  malt according to `docs/assumptions.md`.
- `Net Contents`: submitted container size.
- `Name and Address`: submitted business name plus address evidence.
- `Country of Origin`: use `Domestic` for USA/domestic products; use a country
  name for imports.
- `Malt Added Nonbeverage Alcohol`: malt-only trigger, `Yes` or `No`.
- `Malt Color Additive Applicable`: malt-only trigger, `Yes` or `No`.

Non-malt rows can leave the two malt trigger columns blank.

The current 300-row CSV was generated from the first 300 image filenames in
`data/labels`, sorted alphabetically. Some rows use exact metadata already known
to the repo, while many rows use conservative demo values inferred from
filenames and label families. Treat this as a hosted demo dataset, not certified
ground-truth COLA application data.

## Azure App Context

Observed Azure app setup:

```text
App Service: alv-demo
Resource group: alv-demo-rg
Location: Canada East
Default host: alv-demo-dxhabyf3gpecd6a9.canadaeast-01.azurewebsites.net
Custom host: alcohol-label-verifier.blaise-dev.com
```

At the time this note was written, there was no storage account in
`alv-demo-rg`.

## Azure Storage Layout

Use one Azure Blob Storage container for the large demo dataset:

```text
demo-labels/
  manifest.json
  batch_upload_example.csv
  labels/
    3_steves_winery_2013-07-30.png
    ...
```

Recommended manifest shape:

```json
{
  "name": "Large label batch demo",
  "maxItems": 300,
  "csvUrl": "https://<storage-account>.blob.core.windows.net/demo-labels/batch_upload_example.csv",
  "imagesBaseUrl": "https://<storage-account>.blob.core.windows.net/demo-labels/labels/",
  "images": [
    "3_steves_winery_2013-07-30.png",
    "3_steves_winery_2013-07-30_13158001000072.png"
  ]
}
```

The `images` list should match the `Image` column in the CSV.

## Azure Upload Steps

These commands are the intended setup flow. They have not been run as part of
this note.

```powershell
$rg = "alv-demo-rg"
$location = "canadaeast"
$app = "alv-demo"
$container = "demo-labels"
$storage = "alvdemodata$((Get-Random -Minimum 10000 -Maximum 99999))"
```

Create storage:

```powershell
az storage account create `
  --resource-group $rg `
  --name $storage `
  --location $location `
  --sku Standard_LRS `
  --kind StorageV2 `
  --allow-blob-public-access true

$key = az storage account keys list `
  --resource-group $rg `
  --account-name $storage `
  --query "[0].value" -o tsv

az storage container create `
  --name $container `
  --account-name $storage `
  --account-key $key `
  --public-access blob
```

Generate `manifest.json` locally:

```powershell
$csvPath = "data\batch_upload_example.csv"
$labelsDir = "data\labels"
$baseUrl = "https://$storage.blob.core.windows.net/$container"
$images = (Import-Csv $csvPath).Image

$manifest = [ordered]@{
  name = "Large label batch demo"
  maxItems = 300
  csvUrl = "$baseUrl/batch_upload_example.csv"
  imagesBaseUrl = "$baseUrl/labels/"
  images = $images
} | ConvertTo-Json -Depth 5

$manifest | Set-Content "data\manifest.json" -Encoding UTF8
```

Upload CSV, images, and manifest:

```powershell
az storage blob upload `
  --account-name $storage `
  --account-key $key `
  --container-name $container `
  --name "batch_upload_example.csv" `
  --file $csvPath `
  --content-type "text/csv" `
  --overwrite true

foreach ($image in $images) {
  az storage blob upload `
    --account-name $storage `
    --account-key $key `
    --container-name $container `
    --name "labels/$image" `
    --file (Join-Path $labelsDir $image) `
    --content-type "image/png" `
    --overwrite true
}

az storage blob upload `
  --account-name $storage `
  --account-key $key `
  --container-name $container `
  --name "manifest.json" `
  --file "data\manifest.json" `
  --content-type "application/json" `
  --overwrite true
```

Configure Blob CORS for the hosted app:

```powershell
az storage cors add `
  --account-name $storage `
  --account-key $key `
  --services b `
  --methods GET HEAD OPTIONS `
  --origins "https://alcohol-label-verifier.blaise-dev.com" "https://alv-demo-dxhabyf3gpecd6a9.canadaeast-01.azurewebsites.net" `
  --allowed-headers "*" `
  --exposed-headers "*" `
  --max-age 3600
```

Set the App Service setting that points the app to the manifest:

```powershell
$manifestUrl = "$baseUrl/manifest.json"

az webapp config appsettings set `
  --resource-group $rg `
  --name $app `
  --settings `
    ENVIRONMENT=production `
    DEMO_BATCH_MANIFEST_URL=$manifestUrl
```

Restart the App Service after configuration changes:

```powershell
az webapp restart --resource-group $rg --name $app
```

## Required App Behavior

The code still needs to support the production demo button and manifest loading.
The intended behavior is:

- If `ENVIRONMENT=development`, do not show the large demo batch button.
- If `ENVIRONMENT=production` and `DEMO_BATCH_MANIFEST_URL` is set, show the
  large demo batch button.
- The frontend fetches the manifest.
- The frontend downloads the CSV and image blobs listed in the manifest.
- The frontend loads those files into the same batch upload and matching flow
  used for normal user uploads.
- The backend receives the final matched files and rows through the normal batch
  endpoint.

No extra `DEMO_BATCH_MAX_ITEMS` environment variable is needed. The large demo
limit can come from the manifest and/or a code constant, while the backend still
owns final batch validation.

## Cost Expectation

The local 400-image dataset is roughly 294 MB. A 300-image hosted subset should
be smaller than that. Storage cost for a week should be very low; the main cost
risk is outbound bandwidth if many reviewers repeatedly download the full demo
dataset.
