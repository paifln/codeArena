import { afterEach, expect, it, vi } from "vitest";
import { api, useSession } from "./api";
import { queryClient } from "./lib/queryClient";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  queryClient.clear();
  useSession.getState().setUser(null);
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
    vi
      .fn()
      .mockResolvedValue(
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
