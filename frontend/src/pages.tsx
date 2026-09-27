import {
  ProblemDocuments,
  ImportProblem,
} from "./features/contest/ProblemDocuments";
import { ContestWizard } from "./features/contest/ContestWizard";
import { ContestOptions, defaultOptions } from "./components/ContestOptions";
import {
  PeopleActionDialog,
  type PeopleAction,
} from "./components/PeopleActionDialog";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  Calendar,
  Check,
  CheckCircle2,
  Download,
  Flame,
  Plus,
  Search,
  Trash2,
  Trophy,
  Users,
} from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import { Link, useNavigate } from "react-router-dom";
import { api, downloadCSV, useSession } from "./api";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  Field,
  Heading,
  Loading,
  Modal,
  useAction,
} from "./ui";
export function useList(path: string, enabled = true) {
  return useQuery<any[]>({
    queryKey: [path],
    queryFn: () => api(path),
    enabled,
    refetchInterval: 10000,
  });
}
export function ContestCard({ contest: c }: { contest: any }) {
  const { t, i18n } = useTranslation();
  return (
    <Link className="contest-card" to={`/contests/${c.id}`}>
      <div className="row between">
        <span className="contest-symbol">
          <Trophy size={23} />
        </span>
        <Badge value={c.status} />
      </div>
      <h3>{c.title}</h3>
      {c.description && <p>{c.description}</p>}
      <div className="contest-meta">
        <span>
          <Calendar size={14} />
          {new Date(c.start_time).toLocaleDateString(i18n.language, {
            day: "numeric",
            month: "short",
          })}
        </span>
        <span>
          <BookOpen size={14} />
          {t("problemCount", {
            count: c.problem_count ?? c.problems?.length ?? 0,
          })}
        </span>
      </div>
      <div className="contest-card-footer">
        <span>{t("join")}</span>
        <ArrowRight size={17} />
      </div>
    </Link>
  );
}
export function Dashboard() {
  const { t } = useTranslation();
  const user = useSession((s) => s.user)!;
  const teacher = user.role !== "STUDENT";
  const contests = useList("/contests");
  const metrics = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api("/dashboard"),
    refetchInterval: 10000,
  });
  const submissions = useList("/submissions");
  const rows = submissions.data || [];
  return (
    <>
      <Heading title={t("welcome", { name: user.name.split(" ")[0] })}>
        {teacher && (
          <Link className="button" to="/contests?create=1">
            <Plus size={17} />
            {t("newContest")}
          </Link>
        )}
      </Heading>
      <div className="stats-grid">
        {[
          [Trophy, t("contests"), metrics.data?.contests ?? "—", "mint"],
          [Flame, t("active"), metrics.data?.active_contests ?? "—", "orange"],
          [
            teacher ? Users : BookOpen,
            t(teacher ? "groups" : "submissions"),
            teacher
              ? (metrics.data?.groups ?? "—")
              : (metrics.data?.submissions ?? "—"),
            "blue",
          ],
          [
            CheckCircle2,
            t("accepted"),
            metrics.data?.accepted ?? "—",
            "purple",
          ],
        ].map(([Icon, label, value, color]: any) => (
          <div className="stat-card" key={label}>
            <span className={`stat-icon ${color}`}>
              <Icon size={21} />
            </span>
            <div>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
            <span className="stat-decoration">↗</span>
          </div>
        ))}
      </div>
      <div className="dashboard-columns">
        <section>
          <div className="section-heading">
            <h2>{t("recent")}</h2>
            <Link to="/contests">
              {t("viewAll")} <ArrowRight size={14} />
            </Link>
          </div>
          <ErrorBox error={contests.error} />
          {contests.isPending ? (
            <Loading />
          ) : contests.data?.length ? (
            <div className="cards-grid">
              {contests.data.slice(0, 4).map((c) => (
                <ContestCard key={c.id} contest={c} />
              ))}
            </div>
          ) : (
            <div className="card">
              <Empty title={t("noContests")} hint={t("noContestsHint")}>
                {teacher && (
                  <Link className="button secondary" to="/contests?create=1">
                    <Plus size={16} />
                    {t("newContest")}
                  </Link>
                )}
              </Empty>
            </div>
          )}
        </section>
        <aside>
          <div className="section-heading">
            <h2>{t("activity")}</h2>
            <span className="live-dot" />
          </div>
          <div className="card activity-card">
            {rows.length ? (
              rows.slice(0, 6).map((s) => (
                <Link key={s.id} to="/submissions" className="activity-row">
                  <span
                    className={`activity-icon ${s.status === "ACCEPTED" ? "success" : ""}`}
                  >
                    <Check size={17} />
                  </span>
                  <div>
                    <strong>{s.problem_title || `#${s.problem_id}`}</strong>
                    <small>{s.user_name || user.name}</small>
                    <Badge value={s.status} />
                  </div>
                </Link>
              ))
            ) : (
              <Empty title={t("noActivity")} />
            )}
          </div>
        </aside>
      </div>
    </>
  );
}
const ContestForm = ContestWizard;

export function Contests() {
  const { t } = useTranslation();
  const teacher = useSession((s) => s.user?.role) !== "STUDENT";
  const list = useList("/contests");
  const [create, setCreate] = useState(
    new URLSearchParams(location.search).has("create"),
  );
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  return (
    <>
      <Heading title={t("contests")} subtitle={t("noContestsHint")}>
        {teacher && (
          <Button onClick={() => setCreate(true)}>
            <Plus size={17} />
            {t("newContest")}
          </Button>
        )}
      </Heading>
      <div className="toolbar">
        <div className="tabs">
          {["all", "active", "upcoming", "finished"].map((v) => (
            <button
              className={filter === v ? "selected" : ""}
              key={v}
              onClick={() => setFilter(v)}
            >
              {t(v)}
            </button>
          ))}
        </div>
        <div className="search">
          <Search size={17} />
          <input
            aria-label={t("search")}
            placeholder={t("search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>
      <ErrorBox error={list.error} />
      {list.isPending ? (
        <Loading />
      ) : list.data?.length ? (
        <div className="cards-grid wide">
          {list.data
            .filter(
              (c) =>
                c.title.toLowerCase().includes(search.toLowerCase()) &&
                (filter === "all" ||
                  (filter === "active" &&
                    ["RUNNING", "PAUSED"].includes(c.status)) ||
                  (filter === "upcoming" &&
                    ["DRAFT", "SCHEDULED"].includes(c.status)) ||
                  (filter === "finished" && c.status === "FINISHED")),
            )
            .map((c) => (
              <ContestCard key={c.id} contest={c} />
            ))}
        </div>
      ) : (
        <div className="card">
          <Empty title={t("noContests")} hint={t("noContestsHint")} />
        </div>
      )}
      <Modal
        open={create && teacher}
        onClose={() => setCreate(false)}
        title={t("newContest")}
      >
        <ContestForm close={() => setCreate(false)} />
      </Modal>
    </>
  );
}
function ProblemForm({
  close,
  existing,
}: {
  close: () => void;
  existing?: any;
}) {
  const { t } = useTranslation();
  const a = useAction();
  const q = useQueryClient();
  const [tests, setTests] = useState<any[]>(
    existing?.tests || [
      { input_data: "", expected: "", is_sample: true },
      { input_data: "", expected: "", is_sample: false },
    ],
  );
  const [desc, setDesc] = useState(existing?.description || "");
  const [preview, setPreview] = useState(false);
  const [rejudgeMode, setRejudgeMode] = useState("none");
  const usage = useQuery({
    queryKey: ["problem-usage", existing?.id],
    queryFn: () => api(`/problems/${existing.id}/usage`),
    enabled: !!existing?.id,
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        a.execute(async () => {
          await api(
            existing?.id ? `/problems/${existing.id}` : "/problems",
            {
              title: f.get("title"),
              description: desc,
              editorial: f.get("editorial"),
              input_fmt: f.get("input"),
              output_fmt: f.get("output"),
              difficulty: f.get("difficulty"),
              time_limit: Number(f.get("time")),
              mem_limit: Number(f.get("memory")),
              tags: String(f.get("tags"))
                .split(",")
                .map((v) => v.trim())
                .filter(Boolean),
              tests,
            },
            existing?.id ? "PATCH" : "POST",
          );
          if (existing?.id && rejudgeMode !== "none")
            for (const contest of usage.data?.contests || [])
              await api(`/contests/${contest.id}/rejudge`, {
                problem_id: existing.id,
                affected_only: rejudgeMode === "affected",
              });
          q.invalidateQueries({ queryKey: ["/problems"] });
          close();
        });
      }}
    >
      {usage.data?.count > 0 && (
        <div className="notice warning">
          <p>{t("existingSubmissions", { count: usage.data.count })}</p>
          <select
            aria-label={t("rejudge")}
            value={rejudgeMode}
            onChange={(e) => setRejudgeMode(e.target.value)}
          >
            <option value="none">{t("noRejudge")}</option>
            <option value="affected">{t("rejudgeAffected")}</option>
            <option value="all">{t("rejudgeProblem")}</option>
          </select>
        </div>
      )}
      <Field label={t("title")}>
        <input
          name="title"
          defaultValue={existing?.title}
          required
          maxLength={180}
        />
      </Field>
      <div className="row between">
        <label>{t("description")}</label>
        <Button
          type="button"
          variant="ghost"
          onClick={() => setPreview(!preview)}
        >
          {t(preview ? "edit" : "preview")}
        </Button>
      </div>
      {preview ? (
        <div className="markdown preview">
          <ReactMarkdown>{desc}</ReactMarkdown>
        </div>
      ) : (
        <textarea
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          rows={7}
          minLength={10}
          required
        />
      )}
      <div className="form-grid">
        <Field label={t("input")}>
          <textarea name="input" defaultValue={existing?.input_fmt} rows={3} />
        </Field>
        <Field label={t("output")}>
          <textarea
            name="output"
            defaultValue={existing?.output_fmt}
            rows={3}
          />
        </Field>
      </div>
      {existing?.review_required && (
        <p className="notice warning">{t("importReview")}</p>
      )}
      {existing?.id ? (
        <ProblemDocuments
          key={existing.id}
          problemId={existing.id}
          documents={existing.documents}
          editable
        />
      ) : (
        <p className="muted">{t("documentsSave")}</p>
      )}
      <Field label={t("editorial")}>
        <textarea
          name="editorial"
          rows={5}
          maxLength={30000}
          defaultValue={existing?.editorial || ""}
        />
      </Field>
      <p className="muted">{t("editorialHint")}</p>
      <div className="form-grid three">
        <Field label={t("difficulty")}>
          <select
            name="difficulty"
            defaultValue={existing?.difficulty || "EASY"}
          >
            {["EASY", "MEDIUM", "HARD"].map((x) => (
              <option value={x} key={x}>
                {t(x)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("timeLimit")}>
          <input
            name="time"
            type="number"
            min="0.1"
            max="10"
            step="0.1"
            defaultValue={existing?.time_limit || 2}
          />
        </Field>
        <Field label={t("memoryLimit")}>
          <input
            name="memory"
            type="number"
            min="32"
            max="512"
            defaultValue={existing?.mem_limit || 128}
          />
        </Field>
      </div>
      <Field label={t("tags")}>
        <input name="tags" defaultValue={existing?.tags?.join(", ")} />
      </Field>
      <div className="section-heading">
        <h3>{t("tests")}</h3>
        <label className="button ghost file-upload">
          {t("importTests")}
          <input
            type="file"
            accept="application/json,.json"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file)
                try {
                  const rows = JSON.parse(await file.text());
                  if (
                    !Array.isArray(rows) ||
                    !rows.every(
                      (x) =>
                        typeof x.input_data === "string" &&
                        typeof x.expected === "string" &&
                        typeof x.is_sample === "boolean",
                    )
                  )
                    throw new Error(t("error"));
                  setTests(rows);
                } catch (err) {
                  a.setError(err);
                }
            }}
          />
        </label>
      </div>
      <p className="muted">{t("testHint")}</p>
      {tests.map((test, i) => (
        <div className="test-editor" key={i}>
          <div className="row between">
            <label className="check-row">
              <input
                type="checkbox"
                checked={test.is_sample}
                onChange={(e) =>
                  setTests(
                    tests.map((x, j) =>
                      i === j ? { ...x, is_sample: e.target.checked } : x,
                    ),
                  )
                }
              />
              {t(test.is_sample ? "sample" : "hidden")} #{i + 1}
            </label>
            <button
              className="icon-button"
              type="button"
              aria-label={t("remove")}
              onClick={() => setTests(tests.filter((_, j) => j !== i))}
            >
              <Trash2 size={16} />
            </button>
          </div>
          <Field label={t("weight")}>
            <input
              type="number"
              min={0}
              max={100}
              value={test.weight ?? 1}
              onChange={(e) =>
                setTests(
                  tests.map((x, j) =>
                    i === j ? { ...x, weight: Number(e.target.value) } : x,
                  ),
                )
              }
            />
          </Field>
          <div className="form-grid">
            {["input_data", "expected"].map((key) => (
              <Field
                key={key}
                label={t(key === "input_data" ? "input" : "output")}
              >
                <textarea
                  className="mono"
                  rows={3}
                  value={test[key]}
                  onChange={(e) =>
                    setTests(
                      tests.map((x, j) =>
                        i === j ? { ...x, [key]: e.target.value } : x,
                      ),
                    )
                  }
                />
              </Field>
            ))}
          </div>
        </div>
      ))}
      <Button
        type="button"
        variant="secondary"
        onClick={() =>
          setTests([
            ...tests,
            { input_data: "", expected: "", is_sample: false },
          ])
        }
      >
        <Plus size={15} />
        {t("addTest")}
      </Button>
      <ErrorBox error={a.error} />
      <div className="form-actions">
        <Button type="button" variant="secondary" onClick={close}>
          {t("cancel")}
        </Button>
        <Button
          disabled={
            a.busy || !tests.some((test) => test.is_sample) || desc.length < 10
          }
        >
          {t("save")}
        </Button>
      </div>
    </form>
  );
}
export function Problems() {
  const [importing, setImporting] = useState(false);
  const { t } = useTranslation();
  const list = useList("/problems");
  const [editing, setEditing] = useState<any>(null);
  const [search, setSearch] = useState("");
  const [difficulty, setDifficulty] = useState("all");
  return (
    <>
      <Heading title={t("problems")} subtitle={t("testHint")}>
        <Button variant="secondary" onClick={() => setImporting(true)}>
          {t("importExternal")}
        </Button>
        <Button onClick={() => setEditing({})}>
          <Plus size={17} />
          {t("newProblem")}
        </Button>
      </Heading>
      <div className="toolbar">
        <div className="search">
          <Search size={17} />
          <input
            placeholder={t("search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value)}
        >
          <option value="all">{t("all")}</option>
          {["EASY", "MEDIUM", "HARD"].map((v) => (
            <option value={v} key={v}>
              {t(v)}
            </option>
          ))}
        </select>
      </div>
      <ErrorBox error={list.error} />
      <div className="card table-wrap">
        {list.isPending ? (
          <Loading />
        ) : list.data?.length ? (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>{t("title")}</th>
                <th>{t("difficulty")}</th>
                <th>{t("timeLimit")}</th>
                <th>{t("tests")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data
                .filter(
                  (p) =>
                    p.title.toLowerCase().includes(search.toLowerCase()) &&
                    (difficulty === "all" || p.difficulty === difficulty),
                )
                .map((p) => (
                  <tr key={p.id}>
                    <td className="mono muted">
                      {String(p.id).padStart(3, "0")}
                    </td>
                    <td>
                      <strong>{p.title}</strong>
                      <div className="tags">
                        {p.tags?.map((tag: string) => (
                          <span key={tag}>{tag}</span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <Badge value={p.difficulty} />
                    </td>
                    <td>{p.time_limit}</td>
                    <td>{p.test_count ?? "—"}</td>
                    <td>
                      <Button
                        variant="ghost"
                        onClick={async () =>
                          setEditing(await api(`/problems/${p.id}`))
                        }
                      >
                        {t("edit")}
                      </Button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        ) : (
          <Empty title={t("noProblems")} />
        )}
      </div>
      <Modal
        open={importing}
        onClose={() => setImporting(false)}
        title={t("importExternal")}
      >
        <ImportProblem
          onImported={(value) => {
            setImporting(false);
            setEditing(value);
          }}
        />
      </Modal>
      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={t(editing?.id ? "editProblem" : "newProblem")}
      >
        {editing !== null && (
          <ProblemForm existing={editing} close={() => setEditing(null)} />
        )}
      </Modal>
    </>
  );
}
export function Groups() {
  const { t } = useTranslation();
  const list = useList("/groups");
  const users = useList("/users");
  const [create, setCreate] = useState(false);
  const [selected, setSelected] = useState<any>(null);
  const [credentials, setCredentials] = useState<any[] | null>(null);
  const [peopleAction, setPeopleAction] = useState<PeopleAction | null>(null);
  const a = useAction();
  const q = useQueryClient();
  return (
    <>
      <Heading title={t("groups")} subtitle={t("credentialsHint")}>
        <Button onClick={() => setCreate(true)}>
          <Plus size={17} />
          {t("newGroup")}
        </Button>
      </Heading>
      <ErrorBox error={list.error || users.error} />
      {list.isPending ? (
        <Loading />
      ) : list.data?.length ? (
        <div className="cards-grid wide">
          {list.data.map((g) => (
            <div className="card group-card" key={g.id}>
              <span className="group-icon">
                <Users size={26} />
              </span>
              <h3>{g.name}</h3>
              <p>
                {g.member_count ?? g.student_count ?? g.members?.length ?? 0}{" "}
                {t("students").toLowerCase()}
              </p>
              <Button
                variant="secondary"
                onClick={() => {
                  a.setError(null);
                  setSelected(g);
                }}
              >
                <Plus size={16} />
                {t("addStudents")}
              </Button>
              <Button
                variant="ghost danger"
                onClick={() =>
                  setPeopleAction({ kind: "group", id: g.id, name: g.name })
                }
              >
                <Trash2 size={16} />
                {t("deleteGroup")}
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <div className="card">
          <Empty title={t("noGroups")} />
        </div>
      )}
      {!!users.data?.length && (
        <section className="card table-wrap section-gap">
          <table>
            <thead>
              <tr>
                <th>{t("name")}</th>
                <th>{t("username")}</th>
                <th>{t("groups")}</th>
                <th>{t("actions")}</th>
              </tr>
            </thead>
            <tbody>
              {users.data
                .filter((u) => u.role === "STUDENT")
                .map((u) => (
                  <tr key={u.id}>
                    <td>{u.name}</td>
                    <td className="mono">{u.username}</td>
                    <td>
                      {list.data
                        ?.filter((g) =>
                          g.members?.some((m: any) => m.id === u.id),
                        )
                        .map((g) => g.name)
                        .join(", ") || "?"}
                    </td>
                    <td>
                      <div className="people-actions">
                        <Button
                          variant="ghost"
                          onClick={() =>
                            setPeopleAction({
                              kind: "password",
                              id: u.id,
                              name: u.name,
                            })
                          }
                        >
                          {t("resetPassword")}
                        </Button>
                        <Button
                          variant="ghost danger"
                          onClick={() =>
                            setPeopleAction({
                              kind: "student",
                              id: u.id,
                              name: u.name,
                            })
                          }
                        >
                          <Trash2 size={15} />
                          {t("deleteStudent")}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>
      )}
      {peopleAction && (
        <PeopleActionDialog
          key={`${peopleAction.kind}:${peopleAction.id}`}
          target={peopleAction}
          onClose={() => setPeopleAction(null)}
        />
      )}
      <Modal
        title={t("newGroup")}
        open={create}
        onClose={() => setCreate(false)}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            a.execute(async () => {
              await api("/groups", { name: f.get("name") });
              q.invalidateQueries({ queryKey: ["/groups"] });
              setCreate(false);
            });
          }}
        >
          <Field label={t("groupName")}>
            <input name="name" required />
          </Field>
          <ErrorBox error={a.error} />
          <div className="form-actions">
            <Button disabled={a.busy}>{t("create")}</Button>
          </div>
        </form>
      </Modal>
      <Modal
        title={`${t("addStudents")} · ${selected?.name || ""}`}
        open={!!selected}
        onClose={() => setSelected(null)}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            a.execute(async () => {
              const r = await api(`/groups/${selected.id}/students`, {
                prefix: f.get("prefix"),
                count: Number(f.get("count")),
              });
              setCredentials(r.credentials);
              setSelected(null);
              q.invalidateQueries();
            });
          }}
        >
          <div className="form-grid">
            <Field label={t("prefix")}>
              <input
                name="prefix"
                defaultValue="student"
                pattern="[a-zA-Z0-9_-]+"
                required
              />
            </Field>
            <Field label={t("count")}>
              <input
                name="count"
                type="number"
                min={1}
                max={100}
                defaultValue={30}
              />
            </Field>
          </div>
          <ErrorBox error={a.error} />
          <div className="form-actions">
            <Button disabled={a.busy}>{t("create")}</Button>
          </div>
        </form>
      </Modal>
      <Modal
        title={t("credentials")}
        open={credentials !== null}
        onClose={() => setCredentials(null)}
      >
        <div className="notice warning">{t("credentialsOnce")}</div>
        <Button
          onClick={() =>
            downloadCSV("credentials.csv", [
              [t("username"), t("password")],
              ...(credentials || []).map((c) => [c.username, c.password]),
            ])
          }
        >
          <Download size={17} />
          {t("download")}
        </Button>
        <div className="credentials-list">
          {credentials?.map((c) => (
            <div className="row between mono" key={c.username}>
              <span>{c.username}</span>
              <span>{c.password}</span>
            </div>
          ))}
        </div>
      </Modal>
    </>
  );
}
export function Preferences({
  theme,
  setTheme,
}: {
  theme: string;
  setTheme: (v: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const a = useAction();
  const user = useSession((s) => s.user)!;
  const [done, setDone] = useState(false);
  const [teacher, setTeacher] = useState(false);
  const status = useQuery({
    queryKey: ["status"],
    queryFn: () => api("/auth/status"),
  });
  return (
    <>
      <Heading title={t("settings")} subtitle={t("preferences")} />
      <div className="settings-grid">
        <section className="card settings-card">
          <h2>{t("theme")}</h2>
          <div className="theme-options">
            {["light", "dark", "system"].map((v) => (
              <button
                className={`theme-preview ${v} ${theme === v ? "chosen" : ""}`}
                key={v}
                onClick={() => setTheme(v)}
              >
                <div>
                  <i />
                  <span>
                    <b />
                    <b />
                    <b />
                  </span>
                </div>
                {t(v)}
                {theme === v && <Check size={14} />}
              </button>
            ))}
          </div>
          <Field label={t("language")}>
            <select
              value={i18n.language}
              onChange={(e) => {
                i18n.changeLanguage(e.target.value);
                localStorage.setItem("ca_language", e.target.value);
              }}
            >
              <option value="ru">Русский</option>
              <option value="kk">Қазақша</option>
              <option value="en">English</option>
            </select>
          </Field>
        </section>
        <section className="card settings-card">
          <h2>{t("security")}</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              a.execute(async () => {
                await api("/auth/password", {
                  old_password: f.get("old"),
                  new_password: f.get("new"),
                });
                setDone(true);
              });
            }}
          >
            <Field label={t("oldPassword")}>
              <input
                type="password"
                name="old"
                required
                autoComplete="current-password"
              />
            </Field>
            <Field label={t("newPassword")}>
              <input
                type="password"
                name="new"
                required
                minLength={10}
                autoComplete="new-password"
              />
            </Field>
            <ErrorBox error={a.error} />
            {done && <p className="notice success">{t("saved")}</p>}
            <Button disabled={a.busy}>{t("changePassword")}</Button>
          </form>
        </section>
        {user.role !== "STUDENT" && (
          <section className="card settings-card">
            <h2>Online Judge</h2>
            <div
              className={`notice ${status.data?.judge_available ? "success" : "warning"}`}
            >
              {t(status.data?.judge_available ? "judgeReady" : "judgeOffline")}
            </div>
            <p className="muted">{t("setupJudge")}</p>
          </section>
        )}
        {user.role === "ADMIN" && (
          <section className="card settings-card">
            <h2>{t("teachers")}</h2>
            <Button onClick={() => setTeacher(true)}>
              <Plus size={16} />
              {t("newTeacher")}
            </Button>
          </section>
        )}
      </div>
      <Modal
        open={teacher}
        onClose={() => setTeacher(false)}
        title={t("newTeacher")}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            a.execute(async () => {
              await api("/users", {
                ...Object.fromEntries(f),
                role: "TEACHER",
              });
              setTeacher(false);
            });
          }}
        >
          {["name", "username", "password"].map((v) => (
            <Field key={v} label={t(v)}>
              <input
                name={v}
                type={v === "password" ? "password" : "text"}
                required
                minLength={v === "password" ? 10 : 3}
              />
            </Field>
          ))}
          <ErrorBox error={a.error} />
          <div className="form-actions">
            <Button disabled={a.busy}>{t("create")}</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
