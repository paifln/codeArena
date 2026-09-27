import { afterEach, expect, it, vi } from "vitest";
import { api, useSession } from "./api";
import { queryClient } from "./lib/queryClient";
afterEach(() => {
  document.cookie = "ca_csrf=; Max-Age=0; path=/";
  vi.unstubAllGlobals();
  vi.useRealTimers();
  queryClient.clear();
  useSession.getState().setUser(null);
});
it("rotates an expired session once and retries the original request", async () => {
  document.cookie = "ca_csrf=test-csrf; path=/";
  const fetcher = vi.fn()
    .mockResolvedValueOnce(new Response('{}', { status: 401 }))
    .mockResolvedValueOnce(new Response('{"ok":true}'))
    .mockResolvedValueOnce(new Response('{"id":7}'));
  vi.stubGlobal("fetch", fetcher);
  await expect(api("/auth/me")).resolves.toEqual({id:7});
  expect(fetcher.mock.calls[1][0]).toBe("/api/v1/auth/refresh");
  expect(fetcher.mock.calls[1][1].headers["X-CSRF-Token"]).toBe("test-csrf");
  expect(fetcher).toHaveBeenCalledTimes(3);
});
it("does not refresh rejected login credentials", async () => {
  document.cookie = "ca_csrf=test-csrf; path=/";
  const fetcher = vi.fn().mockResolvedValue(new Response('{"detail":"Invalid login"}', {status:401}));
  vi.stubGlobal("fetch", fetcher);
  await expect(api("/auth/login", {username:"wrong"})).rejects.toMatchObject({status:401});
  expect(fetcher).toHaveBeenCalledTimes(1);
});
it("terminates a hung request with a recoverable timeout", async () => {
  vi.useFakeTimers();
  vi.stubGlobal(
    "fetch",
    vi.fn(
      (_url, options) =>
        new Promise((_resolve, reject) => {
          options.signal.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    ),
  );
  const result = api("/submissions", { source: "print(1)" }).catch((e) => e);
  await vi.advanceTimersByTimeAsync(15000);
  expect(await result).toMatchObject({ code: "REQUEST_TIMEOUT" });
});
it("preserves server error codes and retry delay", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "CONTEST_PAUSED" }), {
        status: 403,
        headers: { "Retry-After": "5" },
      }),
    ),
  );
  await expect(api("/submissions", {})).rejects.toMatchObject({
    code: "CONTEST_PAUSED",
    status: 403,
    retryAfter: 5,
  });
});
it("clears private cached results when accounts change", () => {
  useSession
    .getState()
    .setUser({ id: 1, name: "Admin", username: "admin", role: "ADMIN" });
  queryClient.setQueryData(["submission", 1], { source: "private" });
  useSession
    .getState()
    .setUser({ id: 2, name: "Student", username: "student", role: "STUDENT" });
  expect(queryClient.getQueryData(["submission", 1])).toBeUndefined();
});
