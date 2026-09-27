import { create } from "zustand";
import { clearPrivateQueries } from "./lib/queryClient";
export type User = {
  id: number;
  name: string;
  username: string;
  role: "ADMIN" | "TEACHER" | "STUDENT";
};
export const useSession = create<{
  user: User | null;
  setUser: (user: User | null) => void;
}>((set, get) => ({
  user: null,
  setUser: (user) => {
    if (get().user?.id !== user?.id) clearPrivateQueries();
    set({ user });
  },
}));

export class ApiError extends Error {
  constructor(
    public code: string,
    public status = 0,
    public retryAfter = 0,
  ) {
    super(code);
    this.name = "ApiError";
  }
}
let refreshing: Promise<boolean> | null = null;
async function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    const renew = async () => {
      const csrf = document.cookie
        .split("; ")
        .find((v) => v.startsWith("ca_csrf="))
        ?.slice(8);
      if (!csrf) return false;
      const response = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": decodeURIComponent(csrf) },
        signal: AbortSignal.timeout(15000),
      });
      return response.ok;
    };
    // Serialize rotation across tabs as well as concurrent requests in this tab.
    refreshing = (
      navigator.locks
        ? navigator.locks.request("codearena-refresh", async () => {
            const check = await fetch("/api/v1/auth/me", {
              credentials: "include",
              signal: AbortSignal.timeout(15000),
            });
            return check.ok || renew();
          })
        : renew()
    )
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}
export async function api<T = any>(
  path: string,
  body?: unknown,
  method?: string,
  retried = false,
): Promise<T> {
  const csrf = document.cookie
    .split("; ")
    .find((v) => v.startsWith("ca_csrf="))
    ?.slice(8);
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    /^\/groups\/\d+\/students$/.test(path) || path === "/teams/prepare"
      ? 180000
      : 15000,
  );
  try {
    const r = await fetch("/api/v1" + path, {
      signal: controller.signal,
      method: method || (body === undefined ? "GET" : "POST"),
      credentials: "include",
      headers: {
        ...(body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...(csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}),
      },
      ...(body === undefined
        ? {}
        : { body: body instanceof FormData ? body : JSON.stringify(body) }),
    });
    if (!r.ok) {
      if (
        r.status === 401 &&
        !retried &&
        !["/auth/login", "/auth/setup", "/auth/refresh"].includes(path)
      ) {
        if (await refreshSession()) return api<T>(path, body, method, true);
      }
      if (r.status === 401) useSession.getState().setUser(null);
      const e = await r.json().catch(() => ({ detail: r.statusText }));
      throw new ApiError(
        typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail),
        r.status,
        Number(r.headers.get("Retry-After") || 0),
      );
    }
    return r.status === 204 ? undefined : await r.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      controller.signal.aborted ? "REQUEST_TIMEOUT" : "CONNECTION_LOST",
    );
  } finally {
    clearTimeout(timeout);
  }
}
export function downloadCSV(name: string, rows: unknown[][]) {
  const safe = (v: unknown) => {
    let s = String(v ?? "");
    if (/^[=+\-@]/.test(s)) s = "'" + s;
    return '"' + s.replaceAll('"', '""') + '"';
  };
  const blob = new Blob(
    ["\ufeff" + rows.map((r) => r.map(safe).join(",")).join("\r\n")],
    { type: "text/csv;charset=utf-8" },
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
