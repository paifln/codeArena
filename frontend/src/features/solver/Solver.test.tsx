import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api, useSession } from "../../api";
import "../../i18n";
import { Solver } from "./Solver";
vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));
vi.mock("../../useContestEvents", () => ({ useContestEvents: () => {} }));
vi.mock("../../CodeEditor", () => ({
  default: ({ value, onChange }: any) => (
    <textarea
      aria-label="editor"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));
let contest: any;
let posts: any[];
beforeEach(() => {
  localStorage.clear();
  posts = [];
  useSession
    .getState()
    .setUser({ id: 3, name: "Student", username: "student", role: "STUDENT" });
  contest = {
    id: 1,
    title: "Contest",
    status: "RUNNING",
    execution: { allowed: true, reason: null },
    can_manage: false,
    problems: [],
    end_time: new Date(Date.now() + 600000).toISOString(),
    server_time: new Date().toISOString(),
  };
  vi.mocked(api).mockImplementation(async (path, body) => {
    if (path === "/contests/1") return contest;
    if (path.startsWith("/problems/"))
      return {
        id: 1,
        title: "Sum",
        samples: [],
        description: "Sum",
        input_fmt: "",
        output_fmt: "",
        time_limit: 1,
        mem_limit: 128,
      };
    if (path === "/submissions") {
      posts.push(body);
      return { id: 9, status: "QUEUED" };
    }
    if (path === "/submissions/9")
      return { id: 9, status: "ACCEPTED", tests: [] };
    return {};
  });
});
afterEach(cleanup);
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/contests/1/problems/1"]}>
        <Routes>
          <Route
            path="/contests/:id/problems/:problemId"
            element={<Solver />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}
it("enables Run and Submit after typing and sends distinct request IDs", async () => {
  mount();
  const editor = await screen.findByLabelText("editor");
  const buttons = () =>
    screen
      .getAllByRole("button")
      .filter((b) => b.closest(".editor-actions")) as HTMLButtonElement[];
  expect(buttons().every((b) => b.disabled)).toBe(true);
  fireEvent.change(editor, { target: { value: "print(3)" } });
  await waitFor(() => expect(buttons()[0].disabled).toBe(false));
  fireEvent.click(buttons()[0]);
  await waitFor(() => expect(posts).toHaveLength(1));
  await waitFor(() => expect(buttons()[1].disabled).toBe(false));
  fireEvent.click(buttons()[1]);
  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts.map((p) => p.kind)).toEqual(["RUN", "SUBMIT"]);
  expect(posts[0].request_id).not.toBe(posts[1].request_id);
});
it("explains pause and enables student actions after teacher resumes", async () => {
  contest = {
    ...contest,
    status: "PAUSED",
    execution: { allowed: false, reason: "CONTEST_PAUSED" },
  };
  const client = mount();
  fireEvent.change(await screen.findByLabelText("editor"), {
    target: { value: "print(3)" },
  });
  expect(document.querySelector(".execution-notice")?.textContent).toBeTruthy();
  expect(
    [
      ...document.querySelectorAll<HTMLButtonElement>(".editor-actions button"),
    ].every((b) => b.disabled),
  ).toBe(true);
  contest = {
    ...contest,
    status: "RUNNING",
    execution: { allowed: true, reason: null },
  };
  await act(async () => {
    await client.invalidateQueries({ queryKey: ["contest", "1"] });
  });
  await waitFor(() =>
    expect(
      [
        ...document.querySelectorAll<HTMLButtonElement>(
          ".editor-actions button",
        ),
      ].every((b) => !b.disabled),
    ).toBe(true),
  );
  expect(document.querySelector(".execution-notice")).toBeNull();
});
it("reuses request ID after a lost response and prevents double clicks", async () => {
  let attempts: any[] = [];
  const original = vi.mocked(api).getMockImplementation()!;
  vi.mocked(api).mockImplementation(async (path, body, method) => {
    if (path === "/submissions") {
      attempts.push(body);
      if (attempts.length === 1) throw new Error("Connection lost");
      return { id: 9, status: "QUEUED" };
    }
    return original(path, body, method);
  });
  mount();
  fireEvent.change(await screen.findByLabelText("editor"), {
    target: { value: "print(3)" },
  });
  const run = () =>
    document.querySelector<HTMLButtonElement>(".editor-actions button")!;
  await waitFor(() => expect(run().disabled).toBe(false));
  fireEvent.click(run());
  await waitFor(() =>
    expect(screen.getByRole("alert").textContent).toContain("Connection lost"),
  );
  fireEvent.click(run());
  fireEvent.click(run());
  await waitFor(() => expect(attempts).toHaveLength(2));
  expect(attempts[0].request_id).toBe(attempts[1].request_id);
});
