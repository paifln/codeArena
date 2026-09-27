import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ParticipationPanel } from "./ParticipationPanel";
import { api } from "../../api";
vi.mock("../../api", () => ({ api: vi.fn().mockResolvedValue({}) }));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
function view(pending = 0, completed_at: number | null = null) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ParticipationPanel
          contest={{
            id: 1,
            status: "RUNNING",
            problems: [{ id: 2 }],
            participation: {
              solved: 1,
              total: 1,
              solved_ids: [2],
              team: false,
              pending,
              completed_at,
            },
          }}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
it("requires explicit confirmation before finishing", async () => {
  view();
  fireEvent.click(screen.getByRole("button", { name: "finishParticipation" }));
  expect(api).not.toHaveBeenCalled();
  const buttons = screen.getAllByRole("button", {
    name: "finishParticipation",
  });
  fireEvent.click(buttons[buttons.length - 1]);
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/contests/1/complete", {}),
  );
});
it("waits for judging and presents completion instead of another finish action", () => {
  view(1);
  expect(
    (
      screen.getByRole("button", {
        name: "finishParticipation",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  cleanup();
  view(0, 123);
  expect(
    screen.queryByRole("button", { name: "finishParticipation" }),
  ).toBeNull();
  expect(screen.getByRole("link", { name: "backToContests" })).toBeTruthy();
});
