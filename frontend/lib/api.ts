"use client";

/**
 * Typed fetch wrapper.
 *
 * The browser talks to `/api/*` on its own origin; Next rewrites that to the
 * FastAPI service (see next.config.mjs), so there is no CORS dance and no
 * API host baked into the bundle.
 */

export type Money = { paise: number; rupees: number; display: string; compact: string };

const TOKEN_KEY = "runway.token";
const BIZ_KEY = "runway.business";
const ASOF_KEY = "runway.asof";

export const session = {
  get token() { return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY); },
  get businessId() { return typeof window === "undefined" ? null : localStorage.getItem(BIZ_KEY); },
  get asOf() { return typeof window === "undefined" ? null : localStorage.getItem(ASOF_KEY); },
  set(token: string, businessId: string) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(BIZ_KEY, businessId);
  },
  setBusiness(id: string) { localStorage.setItem(BIZ_KEY, id); },
  setAsOf(d: string | null) {
    if (d) localStorage.setItem(ASOF_KEY, d);
    else localStorage.removeItem(ASOF_KEY);
  },
  clear() { [TOKEN_KEY, BIZ_KEY, ASOF_KEY].forEach((k) => localStorage.removeItem(k)); },
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

function withAsOf(path: string) {
  const asOf = session.asOf;
  if (!asOf) return path;
  return path.includes("?") ? `${path}&as_of=${asOf}` : `${path}?as_of=${asOf}`;
}

async function request<T>(path: string, init: RequestInit = {}, useAsOf = true): Promise<T> {
  const headers = new Headers(init.headers);
  const token = session.token;
  const biz = session.businessId;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (biz) headers.set("X-Business-Id", biz);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const res = await fetch(useAsOf ? withAsOf(path) : path, { ...init, headers, cache: "no-store" });
  const text = await res.text();
  let body: any = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }

  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined" && !path.includes("/auth/login")) {
      session.clear();
      window.location.href = "/login";
    }
    const detail = (body && (body.detail || body.message)) || `Request failed (${res.status})`;
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail), body);
  }
  return body as T;
}

export const api = {
  get: <T,>(p: string) => request<T>(p),
  post: <T,>(p: string, body?: unknown) =>
    request<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T,>(p: string, body?: unknown) =>
    request<T>(p, { method: "PATCH", body: body === undefined ? undefined : JSON.stringify(body) }),
  del: <T,>(p: string) => request<T>(p, { method: "DELETE" }),
  upload: <T,>(p: string, form: FormData) => request<T>(p, { method: "POST", body: form }),
  raw: request,
};

export async function login(email: string, password: string) {
  const r = await request<any>("/api/auth/login", {
    method: "POST", body: JSON.stringify({ email, password }),
  }, false);
  const active = r.businesses?.find((b: any) => b.id === r.active_business_id) ?? r.businesses?.[0];
  session.set(r.token, r.active_business_id ?? "");
  if (active?.is_demo) {
    if (!session.asOf) session.setAsOf("2026-11-07");
  } else {
    session.setAsOf(null);
  }
  return r;
}

export async function register(payload: {
  email: string;
  password: string;
  full_name: string;
  business_name: string;
  industry: string;
  city?: string;
  opening_balance_paise?: number;
  safety_buffer_paise?: number;
}) {
  const r = await request<any>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  }, false);
  session.set(r.token, r.active_business_id ?? "");
  session.setAsOf(null);
  return r;
}
