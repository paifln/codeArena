import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PeopleActionDialog, type PeopleAction } from "./PeopleActionDialog";
import { api } from "../api";
import "../i18n";
vi.mock("../api", async (original) => ({
  ...(await original<typeof import("../api")>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
function mount(kind: PeopleAction["kind"]) {
  const close = vi.fn();
  vi.mocked(api).mockResolvedValue(undefined);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <PeopleActionDialog
        target={{ kind, id: 3, name: "Student" }}
        onClose={close}
      />
    </QueryClientProvider>,
  );
  return close;
}
it("deletes only after explicit confirmation", async () => {
  const close = mount("group");
  expect(api).not.toHaveBeenCalled();
  fireEvent.click(
    document.querySelector<HTMLButtonElement>("button[type=submit]")!,
  );
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/groups/3", undefined, "DELETE"),
  );
  await waitFor(() => expect(close).toHaveBeenCalledOnce());
});
it("rejects different confirmation and clears password after success", async () => {
  mount("password");
  const password = document.querySelector<HTMLInputElement>(
    "input[name=password]",
  )!;
  const repeat =
    document.querySelector<HTMLInputElement>("input[name=repeat]")!;
  fireEvent.change(password, { target: { value: "New-password-123" } });
  fireEvent.change(repeat, { target: { value: "Different-password-123" } });
  fireEvent.submit(document.querySelector("form")!);
  await screen.findByRole("alert");
  expect(api).not.toHaveBeenCalled();
  fireEvent.change(repeat, { target: { value: "New-password-123" } });
  fireEvent.submit(document.querySelector("form")!);
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/users/3/reset-password", {
      new_password: "New-password-123",
    }),
  );
  await screen.findByRole("status");
  expect(document.querySelector("input[type=password]")).toBeNull();
});
