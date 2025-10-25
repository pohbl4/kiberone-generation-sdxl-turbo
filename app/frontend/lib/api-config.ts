const DEFAULT_API_BASE = "http://localhost:8000/api";

function resolveBase(raw?: string | null): string {
  const trimmed = raw?.trim();
  if (trimmed && trimmed.length > 0) {
    return trimmed;
  }
  return DEFAULT_API_BASE;
}

export const API_BASE_RAW = resolveBase(process.env.NEXT_PUBLIC_API_BASE_URL);
export const API_BASE = API_BASE_RAW.replace(/\/$/, "");

const wsRaw = process.env.NEXT_PUBLIC_WS_URL?.trim();
export const WS_BASE_RAW = wsRaw && wsRaw.length > 0 ? wsRaw : "";
