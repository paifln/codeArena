import { ProblemForm } from "./features/problems/ProblemForm";
import { useList } from "./lib/useList";
import { ImportProblem } from "./features/contest/ProblemDocuments";
import { ContestWizard } from "./features/contest/ContestWizard";
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
import { Link } from "react-router-dom";
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
export function ContestCard({ contest: c }: { contest: any }) {
  const { t, i18n } = useTranslation();
  return (
    <Link
      className="contest-card"
      to={c.can_manage ? `/contests/${c.id}/control` : `/contests/${c.id}`}
    >
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
        <span>
          {t(
            c.can_manage
              ? "controlCenter"
              : c.participation?.completed_at || c.status === "FINISHED"
                ? "viewResults"
                : "viewContest",
          )}
        </span>
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
              {contests.data
                .filter((c) => c.status !== "ARCHIVED")
                .slice(0, 4)
                .map((c) => (
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
                <Link
                  key={s.id}
                  to={`/submissions?submission=${s.id}`}
                  className="activity-row"
                >
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

export function Contests() {
  const { t } = useTranslation();
  const teacher = useSession((s) => s.user?.role) !== "STUDENT";
  const list = useList("/contests");
  const [create, setCreate] = useState(
    new URLSearchParams(location.search).has("create"),
  );
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const visible = (list.data || []).filter(
    (c) =>
      c.title.toLowerCase().includes(search.toLowerCase()) &&
      ((filter === "all" && c.status !== "ARCHIVED") ||
        (filter === "active" && ["RUNNING", "PAUSED"].includes(c.status)) ||
        (filter === "upcoming" && ["DRAFT", "SCHEDULED"].includes(c.status)) ||
        (filter === "finished" && c.status === "FINISHED") ||
        (filter === "archived" && c.status === "ARCHIVED")),
  );
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
          {[
            "all",
            "active",
            "upcoming",
            "finished",
            ...(teacher ? ["archived"] : []),
          ].map((v) => (
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
      ) : visible.length ? (
        <div className="cards-grid wide">
          {visible.map((c) => (
            <ContestCard key={c.id} contest={c} />
          ))}
        </div>
      ) : (
        <div className="card">
          <Empty
            title={t(list.data?.length ? "noMatches" : "noContests")}
            hint={list.data?.length ? undefined : t("noContestsHint")}
          >
            <Button
              variant="secondary"
              onClick={() => {
                setSearch("");
                setFilter("all");
              }}
            >
              {t("resetFilters")}
            </Button>
          </Empty>
        </div>
      )}
      <Modal
        open={create && teacher}
        onClose={() => setCreate(false)}
        title={t("newContest")}
      >
        <ContestWizard close={() => setCreate(false)} />
      </Modal>
    </>
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
