export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function findRecord(source: unknown, keys: string[]) {
  if (!isRecord(source)) {
    return null;
  }
  for (const key of keys) {
    const value = source[key];
    if (isRecord(value)) {
      return value;
    }
  }
  return null;
}

export function findNestedRecord(source: unknown, key: string) {
  if (!isRecord(source)) {
    return null;
  }
  const value = source[key];
  return isRecord(value) ? value : null;
}

export function findString(source: unknown, keys: string[]) {
  if (!isRecord(source)) {
    return null;
  }
  for (const key of keys) {
    const value = source[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value;
    }
  }
  return null;
}

export function findNumber(source: unknown, keys: string[]) {
  if (!isRecord(source)) {
    return null;
  }
  for (const key of keys) {
    const value = source[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
  }
  return null;
}

export function findArray(source: unknown, keys: string[]) {
  if (!isRecord(source)) {
    return null;
  }
  for (const key of keys) {
    const value = source[key];
    if (Array.isArray(value)) {
      return value;
    }
  }
  return null;
}
