import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { ProfileMenu } from "./ProfileMenu";
import "../i18n";
const user = {
  id: 1,
  name: "Teacher",
  username: "teacher",
  role: "TEACHER" as const,
};
afterEach(cleanup);
it("opens profile without logging out, then logs out through menu item", async () => {
  const logout = vi.fn().mockResolvedValue(undefined);
  render(<ProfileMenu user={user} onLogout={logout} />);
  const trigger = screen.getByRole("button");
  fireEvent.click(trigger);
  expect(logout).not.toHaveBeenCalled();
  expect(trigger.getAttribute("aria-expanded")).toBe("true");
  fireEvent.click(screen.getByRole("menuitem"));
  await waitFor(() => expect(logout).toHaveBeenCalledTimes(1));
});
it("supports keyboard opening, Escape and outside click", () => {
  render(<ProfileMenu user={user} onLogout={vi.fn()} />);
  const trigger = screen.getByRole("button");
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
  expect(document.activeElement).toBe(screen.getByRole("menuitem"));
  fireEvent.keyDown(screen.getByRole("menuitem"), { key: "Escape" });
  expect(screen.queryByRole("menu")).toBeNull();
  expect(document.activeElement).toBe(trigger);
  fireEvent.click(trigger);
  fireEvent.pointerDown(document.body);
  expect(screen.queryByRole("menu")).toBeNull();
});
it("keeps error visible when sign out fails", async () => {
  render(
    <ProfileMenu
      user={user}
      onLogout={vi.fn().mockRejectedValue(new Error("Network failed"))}
    />,
  );
  fireEvent.click(screen.getByRole("button"));
  fireEvent.click(screen.getByRole("menuitem"));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Network failed",
  );
});
