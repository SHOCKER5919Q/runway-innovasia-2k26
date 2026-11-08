/**
 * The API client.
 *
 * Three behaviours are load-bearing and easy to break silently: the tenant
 * header on every request, the as-of date being appended to reads, and a
 * 401 clearing the session instead of looping.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, session } from "@/lib/api";

function mockFetch(status: number, body: unknown, capture?: (url: string, init: RequestInit) => void) {
  return vi.fn(async (url: string, init: RequestInit = {}) => {
    capture?.(url, init);
    return {
      ok: status >= 200 && status < 300,
      status,
      text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
    } as Response;
  });
}

beforeEach(() => {
  localStorage.clear();
  session.set("test-token", "biz-123");
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("session", () => {
  it("stores and reads the token and business", () => {
    expect(session.token).toBe("test-token");
    expect(session.businessId).toBe("biz-123");
  });

  it("switches business without touching the token", () => {
    session.setBusiness("biz-456");
    expect(session.businessId).toBe("biz-456");
    expect(session.token).toBe("test-token");
  });

  it("clears everything on sign-out", () => {
    session.setAsOf("2026-11-07");
    session.clear();
    expect(session.token).toBeNull();
    expect(session.businessId).toBeNull();
    expect(session.asOf).toBeNull();
  });

  it("removes the as-of override when set back to null", () => {
    session.setAsOf("2026-11-07");
    expect(session.asOf).toBe("2026-11-07");
    session.setAsOf(null);
    expect(session.asOf).toBeNull();
  });
});

describe("request headers", () => {
  it("sends the bearer token and the business id on every call", async () => {
    let seen: RequestInit = {};
    globalThis.fetch = mockFetch(200, { ok: true }, (_u, i) => { seen = i; }) as never;
    await api.get("/api/overview");
    const h = new Headers(seen.headers);
    expect(h.get("Authorization")).toBe("Bearer test-token");
    expect(h.get("X-Business-Id")).toBe("biz-123");
  });

  it("sets a JSON content type for a body but not for FormData", async () => {
    let seen: RequestInit = {};
    globalThis.fetch = mockFetch(200, {}, (_u, i) => { seen = i; }) as never;
    await api.post("/api/scenarios/quick-run", { kind: "revenue_shock" });
    expect(new Headers(seen.headers).get("Content-Type")).toBe("application/json");

    const form = new FormData();
    form.set("adapter", "bank_csv");
    await api.upload("/api/integrations/import", form);
    // The browser must set the multipart boundary itself.
    expect(new Headers(seen.headers).get("Content-Type")).toBeNull();
  });
});

describe("as-of propagation", () => {
  it("appends the pinned date to a read", async () => {
    session.setAsOf("2026-11-07");
    let url = "";
    globalThis.fetch = mockFetch(200, {}, (u) => { url = u; }) as never;
    await api.get("/api/overview");
    expect(url).toBe("/api/overview?as_of=2026-11-07");
  });

  it("uses & when the path already has a query string", async () => {
    session.setAsOf("2026-11-07");
    let url = "";
    globalThis.fetch = mockFetch(200, {}, (u) => { url = u; }) as never;
    await api.get("/api/transactions?page=2");
    expect(url).toBe("/api/transactions?page=2&as_of=2026-11-07");
  });

  it("leaves the path alone when no date is pinned", async () => {
    let url = "";
    globalThis.fetch = mockFetch(200, {}, (u) => { url = u; }) as never;
    await api.get("/api/overview");
    expect(url).toBe("/api/overview");
  });
});

describe("errors", () => {
  it("raises ApiError carrying the server's detail", async () => {
    globalThis.fetch = mockFetch(422, { detail: "unknown scenario kind" }) as never;
    await expect(api.post("/api/scenarios/quick-run", {}))
      .rejects.toThrowError(/unknown scenario kind/);
  });

  it("keeps the status code on the error", async () => {
    globalThis.fetch = mockFetch(403, { detail: "no membership" }) as never;
    try {
      await api.get("/api/overview");
      expect.unreachable("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      expect((e as ApiError).status).toBe(403);
    }
  });

  it("clears the session on 401 so a stale token cannot loop", async () => {
    globalThis.fetch = mockFetch(401, { detail: "expired" }) as never;
    // jsdom has no navigation; swallow the redirect attempt.
    Object.defineProperty(window, "location", {
      value: { href: "" }, writable: true, configurable: true,
    });
    await api.get("/api/overview").catch(() => {});
    expect(session.token).toBeNull();
  });

  it("tolerates a non-JSON error body", async () => {
    globalThis.fetch = mockFetch(500, "upstream exploded") as never;
    await expect(api.get("/api/overview")).rejects.toThrowError();
  });
});
