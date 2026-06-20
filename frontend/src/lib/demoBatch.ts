import type { BeverageClass } from "../types/verification";

export type DemoBatchGridRow = {
  brand: string;
  beverageClass: "" | BeverageClass;
  classType: string;
  abv: string;
  net: string;
  nameAddr: string;
  country: string;
  maltAddedNonbeverageAlcohol: boolean;
  maltColorAdditiveApplicable: boolean;
  file: File;
};

type DemoManifest = {
  name?: string;
  maxItems?: number;
  csvUrl?: string;
  imagesBaseUrl?: string;
  images?: string[];
};

type CsvRow = Record<string, string>;
type PreparedDemoRow = Omit<DemoBatchGridRow, "file"> & {
  imageName: string;
  imageUrl: string;
};

export async function loadDemoBatchRows(manifestUrl: string): Promise<DemoBatchGridRow[]> {
  const manifest = await fetchJson<DemoManifest>(manifestUrl);
  if (!manifest.csvUrl || !manifest.imagesBaseUrl || !Array.isArray(manifest.images)) {
    throw new Error("The demo batch manifest is incomplete.");
  }

  const imagesBaseUrl = manifest.imagesBaseUrl;
  const csvText = await fetchText(manifest.csvUrl);
  const rows = parseCsv(csvText);
  const imageSet = new Set(manifest.images);
  const limit = Math.min(manifest.maxItems ?? rows.length, rows.length);
  const selectedRows = rows.slice(0, limit);

  const preparedRows: PreparedDemoRow[] = selectedRows.map((row) => {
    const imageName = clean(row["Image"]);
    if (!imageName) {
      throw new Error("The demo batch CSV has a row without an Image value.");
    }
    if (!imageSet.has(imageName)) {
      throw new Error(`The demo manifest does not list ${imageName}.`);
    }
    return {
      brand: clean(row["Brand Name"]),
      beverageClass: normalizeBeverageClass(row["Beverage Class"]),
      classType: clean(row["Class Type"]),
      abv: clean(row["Alcohol Content"]),
      net: clean(row["Net Contents"]),
      nameAddr: clean(row["Name and Address"]),
      country: clean(row["Country of Origin"]),
      maltAddedNonbeverageAlcohol: parseYesNo(row["Malt Added Nonbeverage Alcohol"]),
      maltColorAdditiveApplicable: parseYesNo(row["Malt Color Additive Applicable"]),
      imageName,
      imageUrl: joinUrl(imagesBaseUrl, imageName),
    };
  });

  return mapWithConcurrency(preparedRows, 24, async ({ imageName, imageUrl, ...row }) => {
    const file = await fetchImageFile(imageUrl, imageName);
    return {
      ...row,
      file,
    };
  });
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { mode: "cors" });
  if (!response.ok) {
    throw new Error(`Could not load demo manifest (${response.status}).`);
  }
  return (await response.json()) as T;
}

async function fetchText(url: string): Promise<string> {
  const response = await fetch(url, { mode: "cors" });
  if (!response.ok) {
    throw new Error(`Could not load demo CSV (${response.status}).`);
  }
  return response.text();
}

async function fetchImageFile(url: string, fileName: string): Promise<File> {
  const response = await fetch(url, { mode: "cors" });
  if (!response.ok) {
    throw new Error(`Could not load demo image ${fileName} (${response.status}).`);
  }
  const blob = await response.blob();
  return new File([blob], fileName, { type: blob.type || mimeTypeForName(fileName) });
}

function parseCsv(text: string): CsvRow[] {
  const rows = parseCsvRecords(text);
  if (rows.length < 2) return [];
  const headers = rows[0].map(clean);
  return rows
    .slice(1)
    .filter((row) => row.some((value) => clean(value)))
    .map((row) => {
      const record: CsvRow = {};
      headers.forEach((header, index) => {
        record[header] = row[index] ?? "";
      });
      return record;
    });
}

function parseCsvRecords(text: string): string[][] {
  const records: string[][] = [];
  let row: string[] = [];
  let value = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (quoted) {
      if (char === '"' && next === '"') {
        value += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        value += char;
      }
      continue;
    }

    if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(value);
      value = "";
    } else if (char === "\n") {
      row.push(value);
      records.push(row);
      row = [];
      value = "";
    } else if (char !== "\r") {
      value += char;
    }
  }

  if (value || row.length > 0) {
    row.push(value);
    records.push(row);
  }
  return records;
}

function normalizeBeverageClass(value: string | undefined): "" | BeverageClass {
  const normalized = clean(value).toLowerCase();
  if (normalized === "wine") return "wine";
  if (normalized === "spirits" || normalized === "distilled spirits") return "spirits";
  if (normalized === "malt" || normalized === "malt beverage") return "malt";
  return "";
}

function parseYesNo(value: string | undefined): boolean {
  return ["yes", "y", "true", "1"].includes(clean(value).toLowerCase());
}

function clean(value: string | undefined): string {
  return (value ?? "").trim();
}

function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}/${encodeURIComponent(path)}`;
}

async function mapWithConcurrency<T, R>(
  items: T[],
  concurrency: number,
  worker: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let nextIndex = 0;

  await Promise.all(
    Array.from({ length: Math.min(concurrency, items.length) }, async () => {
      while (nextIndex < items.length) {
        const currentIndex = nextIndex;
        nextIndex += 1;
        results[currentIndex] = await worker(items[currentIndex], currentIndex);
      }
    }),
  );

  return results;
}

function mimeTypeForName(fileName: string): string {
  const lower = fileName.toLowerCase();
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  return "image/png";
}
