import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useDraft } from "./useDraft";
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.useRealTimers();
});
it("flushes latest text on navigation without overwriting another problem", () => {
  localStorage.setItem("problem2", "second");
  const first = renderHook(() => useDraft("problem1"));
  act(() => first.result.current.setCode("first"));
  first.unmount();
  const second = renderHook(() => useDraft("problem2"));
  expect(second.result.current.code).toBe("second");
  expect(localStorage.getItem("problem1")).toBe("first");
});
it("reports storage failure while keeping code editable", () => {
  vi.useFakeTimers();
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("quota");
  });
  const hook = renderHook(() => useDraft("problem"));
  act(() => hook.result.current.setCode("print(1)"));
  act(() => vi.advanceTimersByTime(701));
  expect(hook.result.current.saveState).toBe("unavailable");
  expect(hook.result.current.code).toBe("print(1)");
});
