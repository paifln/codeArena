import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ContestWizard } from "./ContestWizard";
import { api } from "../../api";
vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
beforeEach(() => {
  vi.mocked(api).mockImplementation(async (path, body) => {
    if (path === "/problems")
      return [
        { id: 1, title: "Sum" },
        { id: 2, title: "Graph" },
      ];
    if (path === "/groups") return [{ id: 3, name: "Participants" }];
    if (path === "/users") return [];
    if (path === "/contests" && body) return { id: 8 };
    return [];
  });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
it("creates a contest through seven steps and preserves problem order and languages", async () => {
  const closed = vi.fn();
  const query = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={query}>
      <MemoryRouter>
        <ContestWizard close={closed} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(
    (screen.getByRole("button", { name: "next" }) as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  fireEvent.change(screen.getByLabelText("title"), {
    target: { value: "ICPC Campus Cup" },
  });
  fireEvent.click(screen.getByRole("button", { name: "next" }));
  fireEvent.click(screen.getByRole("button", { name: "next" }));
  fireEvent.click(await screen.findByLabelText("Sum"));
  fireEvent.click(screen.getByLabelText("Graph"));
  fireEvent.click(screen.getAllByRole("button", { name: "moveDown" })[0]);
  fireEvent.click(screen.getByRole("button", { name: "next" }));
  fireEvent.click(await screen.findByLabelText("Participants"));
  fireEvent.click(screen.getByRole("button", { name: "next" }));
  fireEvent.click(screen.getByRole("button", { name: "next" }));
  fireEvent.click(screen.getByLabelText("Java 17"));
  fireEvent.click(screen.getByRole("button", { name: "next" }));
  fireEvent.click(screen.getByRole("button", { name: "newContest" }));
  await waitFor(() => expect(closed).toHaveBeenCalled());
  expect(api).toHaveBeenCalledWith(
    "/contests",
    expect.objectContaining({
      title: "ICPC Campus Cup",
      problem_ids: [2, 1],
      group_ids: [3],
      languages: ["python3", "cpp20"],
      freeze_minutes: 60,
      penalty_minutes: 20,
    }),
  );
});
