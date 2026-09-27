import { ParticipationPanel } from "./features/contest/ParticipationPanel";
import { languages } from "./languages";
import { ScoreboardTable } from "./features/contest/Scoreboard";
import { PuzzleCollection } from "./features/contest/Scoreboard";
import { FeedbackForm } from "./components/FeedbackForm";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Download,
  Lock,
  MessageSquare,
  Send,
  Terminal,
  Trophy,
} from "lucide-react";
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { Timer } from "./components/ContestTimer";
import { Results } from "./components/SubmissionResults";

import { api, downloadCSV, useSession } from "./api";
import { useList } from "./lib/useList";
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
import { useContestEvents } from "./useContestEvents";

export function Contest() {
  const { id } = useParams();
  const connected = useContestEvents(id);
  const { t } = useTranslation();
  const teacher = useSession((s) => s.user?.role) !== "STUDENT";
  const contest = useQuery({
    queryKey: ["contest", id],
    queryFn: () => api(`/contests/${id}`),
    refetchInterval: connected ? 30000 : 10000,
  });
  const [tab, setTab] = useState("tasks");
  const me = useSession((s) => s.user);
  const collections = useQuery({
    queryKey: ["standings", id],
    queryFn: () => api(`/contests/${id}/scoreboard`),
    enabled: tab === "puzzles",
  });
  const c = contest.data;
  if (contest.isPending) return <Loading />;
  if (!c) return <ErrorBox error={contest.error} />;
  return (
    <>
      <Link className="back-link" to="/contests">
        <ArrowLeft size={15} />
        {t("contests")}
      </Link>
      <Heading title={c.title} subtitle={c.description}>
        <Badge value={c.status} />
        <Timer contest={c} />
      </Heading>
      {c.can_manage && (
        <Link className="button secondary" to={`/contests/${id}/control`}>
          {t("controlCenter")}
        </Link>
      )}
      <p className="muted">
        {t(c.mode)} / {t(c.scoring)}
        {c.practice_enabled ? ` / ${t("practiceEnabled")}` : ""}
      </p>
      <ParticipationPanel contest={c} />
      {c.rules && (
        <details className="card control-panel">
          <summary>{t("rules")}</summary>
          <p style={{ whiteSpace: "pre-wrap" }}>{c.rules}</p>
        </details>
      )}
      <div className="toolbar contest-tabs">
        <div className="tabs">
          {[
            ["tasks", BookOpen],
            ["submissions", Terminal],
            ["standings", Trophy],
            ["messages", MessageSquare],
            ["puzzles", Trophy],
          ]
            .filter(
              ([name]) =>
                teacher ||
                c.scoreboard_enabled ||
                !["standings", "puzzles"].includes(String(name)),
            )
            .map(([name, Icon]: any) => (
              <button
                key={name}
                className={tab === name ? "selected" : ""}
                onClick={() => setTab(name)}
              >
                <Icon size={16} />
                {t(name)}
              </button>
            ))}
        </div>
        <span className="live-label">
          <i style={{ background: connected ? undefined : "var(--warning)" }} />
          {t(connected ? "live" : "reconnecting")}
        </span>
      </div>
      {tab === "tasks" && (
        <div className="card">
          {c.problems?.length ? (
            <div className="problem-list">
              {c.problems.map((p: any, i: number) => (
                <Link
                  to={`/contests/${id}/problems/${p.id}`}
                  className="problem-row"
                  key={p.id}
                >
                  <span className="problem-letter">
                    {p.letter || String.fromCharCode(65 + i)}
                  </span>
                  <div>
                    <h3>{p.title}</h3>
                    {c.participation?.solved_ids.includes(p.id) ? (
                      <Badge value="ACCEPTED" />
                    ) : c.participation?.last_verdicts[p.id] ? (
                      <Badge value={c.participation.last_verdicts[p.id]} />
                    ) : (
                      <span className="muted">{t("continueSolving")}</span>
                    )}
                  </div>
                  {p.difficulty && <Badge value={p.difficulty} />}
                  <ArrowRight size={18} />
                </Link>
              ))}
            </div>
          ) : (
            <Empty title={t("notStarted")} />
          )}
        </div>
      )}
      {tab === "submissions" && (
        <>
          {teacher && <Monitor id={id!} />}
          <Submissions contestId={id} />
        </>
      )}
      {tab === "standings" && <Standings id={id!} />}
      {tab === "messages" && <Messages id={id!} teacher={teacher} />}
      {tab === "puzzles" && (
        <>
          <ErrorBox error={collections.error} />
          <div className="puzzle-gallery">
            {collections.data?.rows
              .filter(
                (r: any) =>
                  teacher ||
                  r.user_id === me?.id ||
                  c.teams?.some(
                    (team: any) =>
                      team.id === r.team_id && team.user_ids.includes(me?.id),
                  ),
              )
              .map((row: any) => (
                <PuzzleCollection
                  key={`${row.team_id}:${row.user_id}`}
                  row={row}
                  data={collections.data}
                />
              ))}
          </div>
        </>
      )}
    </>
  );
}
function Monitor({ id }: { id: string }) {
  const { t } = useTranslation();
  const data = useQuery({
    queryKey: ["monitor", id],
    queryFn: () => api(`/contests/${id}/monitor`),
    refetchInterval: 10000,
  });
  const [search, setSearch] = useState("");
  return (
    <section className="section-gap">
      <Heading title={t("participants")} subtitle={t("heartbeatHint")} />
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder={t("search")}
        aria-label={t("search")}
      />
      <ErrorBox error={data.error} />
      {data.data && (
        <div className="card table-wrap section-gap">
          <table>
            <thead>
              <tr>
                <th>{t("name")}</th>
                <th>{t("connection")}</th>
                <th>{t("solved")}</th>
                <th>{t("lastActivity")}</th>
              </tr>
            </thead>
            <tbody>
              {data.data.participants
                .filter((u: any) =>
                  `${u.name} ${u.username}`
                    .toLowerCase()
                    .includes(search.toLowerCase()),
                )
                .map((u: any) => (
                  <tr key={u.id}>
                    <td>
                      {u.name}
                      <small className="block muted">{u.username}</small>
                    </td>
                    <td>
                      <span className={`badge ${u.online ? "success" : ""}`}>
                        <span className="status-dot" />
                        {t(u.online ? "online" : "away")}
                      </span>
                    </td>
                    <td>
                      {data.data.rows.find((r: any) => r.user_id === u.id)
                        ?.solved ?? 0}
                    </td>
                    <td className="muted">
                      {u.last_activity
                        ? new Date(u.last_activity).toLocaleString()
                        : "—"}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="section-gap" />
    </section>
  );
}
export function Standings({ id }: { id: string }) {
  const { t } = useTranslation();
  const data = useQuery({
    queryKey: ["standings", id],
    queryFn: () => api(`/contests/${id}/scoreboard`),
    refetchInterval: 5000,
  });
  if (data.isPending) return <Loading />;
  const s = data.data;
  return (
    <>
      <ErrorBox error={data.error} />
      {s && (
        <>
          {s.frozen && (
            <div className="notice warning">
              <Lock size={16} />
              {t("frozen")}
            </div>
          )}
          <div className="row standings-actions">
            <Button
              variant="secondary"
              onClick={() =>
                downloadCSV("standings.csv", [
                  [
                    t("name"),
                    t("solved"),
                    t(s.scoring === "PARTIAL" ? "points" : "penalty"),
                    ...s.problems.map((p: any) => p.letter),
                  ],
                  ...s.rows.map((r: any) => [
                    r.name,
                    r.solved,
                    s.scoring === "PARTIAL" ? r.score : r.penalty,
                    ...r.cells.map((c: any) =>
                      s.scoring === "PARTIAL"
                        ? c.score
                        : c.solved
                          ? `+${c.attempts} (${c.minutes})`
                          : c.attempts
                            ? `-${c.attempts}`
                            : "",
                    ),
                  ]),
                ])
              }
            >
              <Download size={15} />
              {t("download")}
            </Button>
            <Button variant="secondary" onClick={() => window.print()}>
              {t("print")}
            </Button>
          </div>
          <ScoreboardTable data={s} />
        </>
      )}
    </>
  );
}
export function Submissions({ contestId }: { contestId?: string }) {
  const { t } = useTranslation();
  const teacher = useSession((s) => s.user?.role) !== "STUDENT";
  const [selected, setSelected] = useState<number | null>(() => {
    const id = Number(new URLSearchParams(location.search).get("submission"));
    return Number.isSafeInteger(id) && id > 0 ? id : null;
  });
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [chosenContest, setChosenContest] = useState(contestId || "");
  const [team, setTeam] = useState("");
  const [problem, setProblem] = useState("");
  const [language, setLanguage] = useState("");
  const [after, setAfter] = useState("");
  const [before, setBefore] = useState("");
  const [offset, setOffset] = useState(0);
  const contests = useList("/contests", !contestId);
  const metadata = useQuery({
    queryKey: ["contest", chosenContest],
    queryFn: () => api(`/contests/${chosenContest}`),
    enabled: !!chosenContest,
  });
  useEffect(
    () => setOffset(0),
    [chosenContest, team, problem, language, after, before, filter],
  );
  const params = new URLSearchParams({ limit: "100", offset: String(offset) });
  if (chosenContest) params.set("contest_id", chosenContest);
  if (team) params.set("team_id", team);
  if (problem) params.set("problem_id", problem);
  if (language) params.set("language", language);
  if (filter) params.set("status", filter);
  if (after) params.set("after", String(new Date(after).getTime() / 1000));
  if (before) params.set("before", String(new Date(before).getTime() / 1000));
  const list = useList("/submissions?" + params.toString());
  const detail = useQuery({
    queryKey: ["submission", selected],
    queryFn: () => api(`/submissions/${selected}`),
    enabled: selected !== null,
    refetchInterval: (q) =>
      ["QUEUED", "RUNNING"].includes(q.state.data?.status) ? 1500 : false,
  });
  const a = useAction();
  const qc = useQueryClient();
  return (
    <>
      {!contestId && <Heading title={t("submissions")} subtitle={t("live")} />}
      <div className="toolbar">
        {!contestId && (
          <select
            aria-label={t("contests")}
            value={chosenContest}
            onChange={(e) => {
              setChosenContest(e.target.value);
              setTeam("");
              setProblem("");
            }}
          >
            <option value="">
              {t("contests")}: {t("all")}
            </option>
            {contests.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        )}
        <select
          aria-label={t("teams")}
          value={team}
          onChange={(e) => setTeam(e.target.value)}
        >
          <option value="">
            {t("teams")}: {t("all")}
          </option>
          {metadata.data?.teams?.map((x: any) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </select>
        <select
          aria-label={t("problems")}
          value={problem}
          onChange={(e) => setProblem(e.target.value)}
        >
          <option value="">
            {t("problems")}: {t("all")}
          </option>
          {metadata.data?.problems?.map((x: any) => (
            <option key={x.id} value={x.id}>
              {x.letter}. {x.title}
            </option>
          ))}
        </select>
        <select
          aria-label={t("languages")}
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          <option value="">
            {t("languages")}: {t("all")}
          </option>
          {Object.keys(languages).map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
        <input
          aria-label={t("fromTime")}
          type="datetime-local"
          value={after}
          onChange={(e) => setAfter(e.target.value)}
        />
        <input
          aria-label={t("untilTime")}
          type="datetime-local"
          value={before}
          onChange={(e) => setBefore(e.target.value)}
        />

        <input
          className="submission-search"
          placeholder={t("search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          aria-label={t("filter")}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="">{t("all")}</option>
          {[
            "QUEUED",
            "RUNNING",
            "ACCEPTED",
            "PARTIAL",
            "WRONG_ANSWER",
            "TIME_LIMIT_EXCEEDED",
            "MEMORY_LIMIT_EXCEEDED",
            "RUNTIME_ERROR",
            "COMPILATION_ERROR",
            "SYSTEM_ERROR",
            "OUTPUT_LIMIT_EXCEEDED",
          ].map((v) => (
            <option key={v} value={v}>
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
                <th>{t("time")}</th>
                <th>{t("memory")}</th>
                {teacher && <th>{t("participants")}</th>}
                <th>{t("tasks")}</th>
                <th>{t("result")}</th>
                <th>{t("elapsed")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data
                .filter(
                  (s) =>
                    (!filter || s.status === filter) &&
                    `${s.problem_title || ""} ${s.user_name || ""}`
                      .toLowerCase()
                      .includes(search.toLowerCase()),
                )
                .map((s) => (
                  <tr key={s.id}>
                    <td className="mono muted">#{s.id}</td>
                    <td className="mono muted">
                      {new Date(s.created_at).toLocaleTimeString()}
                    </td>
                    <td className="mono">{s.memory_kb} KB</td>
                    {teacher && <td>{s.user_name || s.user_id}</td>}
                    <td>
                      <strong>{s.problem_title || `#${s.problem_id}`}</strong>
                      <small className="block muted">
                        {s.kind === "RUN" ? t("run") : s.language}{" "}
                        {s.is_practice && ` ? ${t("practice")}`}
                      </small>
                    </td>
                    <td>
                      <Badge value={s.status} />
                    </td>
                    <td className="mono">
                      {s.time_ms != null ? `${s.time_ms} ms` : "—"}
                    </td>
                    <td>
                      <Button variant="ghost" onClick={() => setSelected(s.id)}>
                        {t("code")}
                      </Button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        ) : (
          <Empty title={t("noActivity")} />
        )}
      </div>
      <div className="row standings-actions">
        <Button
          variant="secondary"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 100))}
        >
          {t("previous")}
        </Button>
        <span>
          {offset + 1}?{offset + (list.data?.length || 0)}
        </span>
        <Button
          variant="secondary"
          disabled={(list.data?.length || 0) < 100}
          onClick={() => setOffset(offset + 100)}
        >
          {t("next")}
        </Button>
      </div>
      <Modal
        title={`${t("submissions")} #${selected}`}
        open={selected !== null}
        onClose={() => setSelected(null)}
      >
        {detail.isPending ? (
          <Loading />
        ) : (
          <>
            <ErrorBox error={detail.error} />
            {detail.data && (
              <>
                <div className="row between">
                  <Badge value={detail.data.status} />
                  {teacher && (
                    <Button
                      variant="secondary"
                      disabled={a.busy}
                      onClick={() =>
                        a.execute(async () => {
                          await api(`/submissions/${selected}/rejudge`, {});
                          qc.invalidateQueries();
                        })
                      }
                    >
                      {t("rejudge")}
                    </Button>
                  )}
                </div>
                <ErrorBox error={a.error} />
                <pre className="source-preview">{detail.data.source}</pre>
                {teacher && detail.data.code_review && (
                  <section className="card control-panel">
                    <h3>{t("codeReview")}</h3>
                    <p className="muted">{t("codeReviewHint")}</p>
                    {detail.data.code_review.findings.length ? (
                      detail.data.code_review.findings.map(
                        (f: any, i: number) => (
                          <div key={i}>
                            <strong>
                              L{f.line}: {t(f.rule)}
                            </strong>
                            <pre>{f.excerpt}</pre>
                          </div>
                        ),
                      )
                    ) : (
                      <p>{t("noCodeMarkers")}</p>
                    )}
                  </section>
                )}
                <Results result={detail.data} />
                {teacher && detail.data.history?.length > 0 && (
                  <details>
                    <summary>{t("rejudge")}</summary>
                    {detail.data.history.map((h: any, i: number) => (
                      <p key={i}>
                        {t(h.status)} ?{" "}
                        {t(
                          detail.data.history[i + 1]?.status ||
                            detail.data.status,
                        )}{" "}
                        ? {new Date(h.rejudged_at * 1000).toLocaleString()} ?{" "}
                        {t("rejudgedBy")}: #{h.rejudged_by || "?"}
                      </p>
                    ))}
                  </details>
                )}
                {teacher && (
                  <FeedbackForm
                    key={detail.data.id}
                    id={detail.data.id}
                    feedback={detail.data.feedback || ""}
                  />
                )}
              </>
            )}
          </>
        )}
      </Modal>
    </>
  );
}
export function Messages({ id, teacher }: { id: string; teacher: boolean }) {
  const { t } = useTranslation();
  const announcements = useList(`/contests/${id}/announcements`);
  const clarifications = useList(`/contests/${id}/clarifications`);
  const q = useQueryClient();
  const a = useAction();
  const [answer, setAnswer] = useState<any>(null);
  const contest = useQuery({
    queryKey: ["contest", id],
    queryFn: () => api(`/contests/${id}`),
  });
  return (
    <div className="messages-grid">
      <section>
        <h2>{t("notifications")}</h2>
        {teacher && (
          <form
            className="card message-form"
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const f = new FormData(form);
              a.execute(async () => {
                await api(`/contests/${id}/announcements`, {
                  message: f.get("message"),
                  level: f.get("level"),
                });
                form.reset();
                q.invalidateQueries();
              });
            }}
          >
            <Field label={t("announce")}>
              <textarea name="message" required rows={3} />
            </Field>
            <div className="row between">
              <select name="level">
                <option>INFO</option>
                <option>WARNING</option>
                <option>IMPORTANT</option>
              </select>
              <Button disabled={a.busy}>
                <Send size={15} />
                {t("send")}
              </Button>
            </div>
          </form>
        )}
        {announcements.data?.map((n) => (
          <article className="card message-card" key={n.id}>
            <span className="eyebrow">{n.level}</span>
            <p>{n.message}</p>
            <small className="muted">
              {new Date(n.created_at).toLocaleString()}
            </small>
          </article>
        ))}
        {!announcements.data?.length && <Empty title={t("empty")} />}
      </section>
      <section>
        <h2>{t("question")}</h2>
        {!teacher && (
          <form
            className="card message-form"
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const f = new FormData(form);
              a.execute(async () => {
                await api(`/contests/${id}/clarifications`, {
                  question: f.get("question"),
                  problem_id: f.get("problem_id")
                    ? Number(f.get("problem_id"))
                    : null,
                });
                form.reset();
                q.invalidateQueries();
              });
            }}
          >
            <Field label={t("problems")}>
              <select name="problem_id">
                <option value="">{t("general")}</option>
                {contest.data?.problems?.map((p: any) => (
                  <option key={p.id} value={p.id}>
                    {p.letter}. {p.title}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("ask")}>
              <textarea name="question" required rows={3} />
            </Field>
            <Button disabled={a.busy}>
              <Send size={15} />
              {t("send")}
            </Button>
          </form>
        )}
        {clarifications.data?.map((c) => (
          <article className="card message-card" key={c.id}>
            <strong>{c.user_name || t("question")}</strong>
            <small className="block muted">
              #{c.id} ? {t(c.status || "OPEN")}{" "}
              {c.problem_id
                ? `? ${contest.data?.problems?.find((p: any) => p.id === c.problem_id)?.letter || ""}`
                : ""}
            </small>
            <p>{c.question}</p>
            {teacher && c.status === "OPEN" && (
              <Button
                variant="ghost"
                disabled={a.busy}
                onClick={() =>
                  a.execute(async () => {
                    await api(`/clarifications/${c.id}/dismiss`, {});
                    q.invalidateQueries();
                  })
                }
              >
                {t("dismiss")}
              </Button>
            )}
            {c.answer ? (
              <div className="answer">
                <strong>
                  {t("answer")} {c.is_public && `· ${t("public")}`}
                </strong>
                <p>{c.answer}</p>
              </div>
            ) : (
              <span className="muted">{t("unanswered")}</span>
            )}
            {teacher && (
              <Button variant="ghost" onClick={() => setAnswer(c)}>
                {t("answer")}
              </Button>
            )}
          </article>
        ))}
        {!clarifications.data?.length && <Empty title={t("empty")} />}
      </section>
      <ErrorBox error={a.error} />
      <Modal
        title={t("answer")}
        open={!!answer}
        onClose={() => setAnswer(null)}
      >
        <p>{answer?.question}</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            a.execute(async () => {
              await api(
                `/clarifications/${answer.id}`,
                {
                  answer: f.get("answer"),
                  is_public: f.get("public") === "on",
                },
                "PATCH",
              );
              setAnswer(null);
              q.invalidateQueries();
            });
          }}
        >
          <textarea
            name="answer"
            required
            defaultValue={answer?.answer}
            rows={4}
          />
          <label className="check-row">
            <input
              name="public"
              type="checkbox"
              defaultChecked={answer?.is_public}
            />
            {t("public")}
          </label>
          <Button disabled={a.busy}>{t("send")}</Button>
          <ErrorBox error={a.error} />
        </form>
      </Modal>
    </div>
  );
}
