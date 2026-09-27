import { ContestDetailsForm } from "./ContestDetailsForm";
import { languages as languageCatalog } from "../../languages";
import { useState, useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { QRCodeSVG } from "qrcode.react";
import { api } from "../../api";
import {
  Badge,
  Button,
  ErrorBox,
  Field,
  Heading,
  Loading,
  useAction,
} from "../../ui";
import { Timer } from "../../components/ContestTimer";
import { Messages, Submissions, Standings } from "../../contest";
import { useContestEvents } from "../../useContestEvents";
import { PuzzleCollection } from "./Scoreboard";
import { ReplayReveal } from "./ReplayReveal";

export function PuzzleDesk({ id }: { id: string }) {
  const { t } = useTranslation();
  const q = useQueryClient();
  const a = useAction();
  const [filter, setFilter] = useState("WAITING");
  const query = useQuery({
    queryKey: ["puzzles", id],
    queryFn: () => api<any[]>(`/contests/${id}/puzzles`),
    refetchInterval: 15000,
  });
  return (
    <section>
      <Heading
        title={t("puzzleDesk")}
        subtitle={`${t("waiting")}: ${query.data?.filter((r) => r.status === "WAITING" && !r.revoked).length || 0}`}
      />
      <div className="tabs">
        {["WAITING", "DELIVERED", ""].map((v) => (
          <button
            key={v}
            className={filter === v ? "selected" : ""}
            onClick={() => setFilter(v)}
          >
            {t(
              v === "WAITING"
                ? "waiting"
                : v === "DELIVERED"
                  ? "delivered"
                  : "all",
            )}
          </button>
        ))}
      </div>
      <ErrorBox error={query.error || a.error} />
      <div className="puzzle-desk-grid">
        {query.data
          ?.filter((r) => !filter || r.status === filter)
          .map((r) => (
            <article
              className={`card delivery-card ${r.revoked ? "revoked" : ""}`}
              key={r.id}
            >
              <span
                className={`problem-letter puzzle-color-${(r.letter.charCodeAt(0) - 65) % 6}`}
              >
                {r.letter}
              </span>
              <div>
                <h3>{r.name}</h3>
                <small>
                  {new Date(r.solved_at * 1000).toLocaleTimeString()}
                </small>
                {r.revoked && <p className="notice warning">{t("revoked")}</p>}
                {r.delivered_at && (
                  <small className="block muted">
                    {new Date(r.delivered_at * 1000).toLocaleTimeString()} · #
                    {r.delivered_by}
                  </small>
                )}
              </div>
              <Button
                disabled={a.busy || r.status === "DELIVERED" || r.revoked}
                onClick={() =>
                  a.execute(async () => {
                    await api(`/puzzles/${r.id}/delivered`, {});
                    q.invalidateQueries({ queryKey: ["puzzles", id] });
                  })
                }
              >
                {t("delivered")}
              </Button>
            </article>
          ))}
      </div>
    </section>
  );
}

export function PuzzleDeskPage() {
  const { id } = useParams();
  useContestEvents(id);
  return <PuzzleDesk id={id!} />;
}

export function ControlCenter() {
  const { id } = useParams();
  const { t } = useTranslation();
  const connected = useContestEvents(id);
  const q = useQueryClient();
  const a = useAction();
  const [tab, setTab] = useState("overview");
  const [address, setAddress] = useState(
    () => localStorage.getItem("ca_lan_address") || location.origin,
  );
  const [publicPreview, setPublicPreview] = useState(false);
  const server = useQuery({
    queryKey: ["server"],
    queryFn: () => api("/server"),
  });
  useEffect(() => {
    if (server.data?.detected && !localStorage.getItem("ca_lan_address"))
      setAddress(server.data.address);
  }, [server.data]);
  const contest = useQuery({
    queryKey: ["contest", id],
    queryFn: () => api(`/contests/${id}`),
    refetchInterval: connected ? 30000 : 10000,
  });
  const data = useQuery({
    queryKey: ["control", id],
    queryFn: () => api(`/contests/${id}/control`),
    refetchInterval: connected ? 30000 : 10000,
  });
  const board = useQuery({
    queryKey: ["public-board", id],
    queryFn: () => api(`/contests/${id}/public-scoreboard`),
    enabled: tab === "teams" || publicPreview,
    refetchInterval: 30000,
  });
  const control = (action: string) =>
    a.execute(async () => {
      if (action === "finish" && !confirm(t("confirmFinish"))) return;
      await api(
        `/contests/${id}/${action}`,
        action === "extend" ? { minutes: 15 } : {},
      );
      q.invalidateQueries({ queryKey: ["contest", id] });
      q.invalidateQueries({ queryKey: ["control", id] });
    });
  const rejudge = (problem_id?: number) =>
    a.execute(async () => {
      if (!confirm(t("rejudgeConfirm"))) return;
      await api(`/contests/${id}/rejudge`, {
        problem_id: problem_id ?? null,
        affected_only: false,
      });
      q.invalidateQueries({ queryKey: ["control", id] });
    });
  if (contest.isPending || data.isPending) return <Loading />;
  if (!contest.data || !data.data)
    return <ErrorBox error={contest.error || data.error} />;
  const c = contest.data;
  const d = data.data;
  let validAddress = false;
  try {
    const url = new URL(address);
    validAddress =
      ["http:", "https:"].includes(url.protocol) &&
      !url.username &&
      !url.password &&
      !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  } catch {}
  return (
    <>
      <Link className="back-link" to={`/contests/${id}`}>
        ← {t("contests")}
      </Link>
      <Heading title={c.title} subtitle={t("controlCenter")}>
        <Badge value={c.status} />
        <Timer contest={c} />
      </Heading>
      <div className="contest-controls">
        {(c.status === "RUNNING"
          ? ["pause", "extend", "finish"]
          : c.status === "PAUSED"
            ? ["resume", "extend", "finish"]
            : ["DRAFT", "SCHEDULED"].includes(c.status)
              ? ["start"]
              : []
        ).map((v) => (
          <Button
            key={v}
            variant="secondary"
            disabled={a.busy}
            onClick={() => control(v)}
          >
            {t(v)}
          </Button>
        ))}
        <Button
          variant="secondary"
          disabled={
            a.busy || (!c.frozen && !["RUNNING", "PAUSED"].includes(c.status))
          }
          onClick={() => control(c.frozen ? "unfreeze" : "freeze")}
        >
          {t(c.frozen ? "unfreeze" : "freeze")}
        </Button>
        <span className="live-label">
          <i />
          {t(connected ? "live" : "reconnecting")}
        </span>
      </div>
      {["FINISHED", "ARCHIVED"].includes(c.status) && (
        <Button
          variant="secondary"
          disabled={a.busy}
          onClick={() => {
            if (c.status === "FINISHED" && !confirm(t("archiveConfirm")))
              return;
            control(c.status === "ARCHIVED" ? "restore" : "archive");
          }}
        >
          {t(c.status === "ARCHIVED" ? "restoreContest" : "archiveContest")}
        </Button>
      )}
      <ErrorBox error={a.error} />
      <nav className="tabs control-tabs" aria-label={t("controlCenter")}>
        {[
          "overview",
          "standings",
          "submissions",
          "teams",
          "problems",
          "messages",
          "puzzles",
          "replay",
          "settings",
        ].map((v) => (
          <button
            key={v}
            className={tab === v ? "selected" : ""}
            onClick={() => setTab(v)}
          >
            {t(v)}
            {v === "messages" && d.open_questions > 0 && (
              <span className="count-pill">{d.open_questions}</span>
            )}
          </button>
        ))}
      </nav>
      {tab === "overview" && (
        <>
          <div className="control-metrics">
            {[
              [
                t("teams"),
                `${d.teams.filter((x: any) => x.online).length}/${d.teams.length}`,
              ],
              [t("submissions"), d.total_submissions],
              [t("pendingJobs"), d.queued + d.judging],
              [t("openQuestions"), d.open_questions],
            ].map(([label, value]) => (
              <article className="card metric" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </article>
            ))}
          </div>
          <div className="control-columns">
            <section className="card control-panel">
              <h2>{t("timeline")}</h2>
              <div className="event-list">
                {d.events.length ? (
                  d.events.map((e: any) => (
                    <article key={e.id}>
                      <time>
                        {new Date(e.time * 1000).toLocaleTimeString()}
                      </time>
                      <div>
                        <strong>{t(e.type)}</strong>
                        <small className="block muted">
                          {e.detail?.name || ""} {e.detail?.letter || ""}{" "}
                          {e.detail?.status ? t(e.detail.status) : ""}{" "}
                        </small>
                      </div>
                    </article>
                  ))
                ) : (
                  <p>{t("noEvents")}</p>
                )}
              </div>
            </section>
            <section className="card control-panel">
              <h2>{t("checkingSolutions")}</h2>
              <p>
                <strong>
                  {t(
                    d.judge.judge_available
                      ? "checkingAvailable"
                      : "checkingUnavailable",
                  )}
                </strong>
              </p>
              {d.alerts.disconnected.map((name: string) => (
                <p key={name} className="notice warning">
                  {name}: {t("away")}
                </p>
              ))}
              {d.alerts.slow_submissions.map((sid: number) => (
                <p key={sid} className="notice warning">
                  #{sid}: {t("judging")}
                </p>
              ))}
              <ProblemStats problems={d.problems} compact />
            </section>
          </div>
        </>
      )}
      {tab === "standings" && (
        <>
          <div className="row standings-actions">
            <Button
              variant="secondary"
              onClick={() => setPublicPreview(!publicPreview)}
            >
              {t(publicPreview ? "adminBoard" : "publicBoard")}
            </Button>
            <Link
              target="_blank"
              className="button secondary"
              to={
                c.public_scoreboard
                  ? `/display/contests/${id}/scoreboard`
                  : `/contests/${id}/control`
              }
              onClick={(e) => {
                if (!c.public_scoreboard) {
                  e.preventDefault();
                  setTab("settings");
                }
              }}
            >
              {t("projector")}
            </Link>
          </div>
          {publicPreview ? (
            board.data && <PublicBoard data={board.data} />
          ) : (
            <Standings id={id!} />
          )}
        </>
      )}
      {tab === "submissions" && (
        <>
          <Button
            variant="secondary"
            disabled={a.busy}
            onClick={() => rejudge()}
          >
            {t("rejudgeAll")}
          </Button>
          <Submissions contestId={id} />
        </>
      )}
      {tab === "teams" && (
        <>
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t("participants")}</th>
                  <th>{t("status")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {d.teams.map((team: any) => (
                  <tr key={team.identity}>
                    <td>{team.name}</td>
                    <td>
                      {t(
                        team.completed_at
                          ? "participationComplete"
                          : team.online
                            ? "online"
                            : "offline",
                      )}
                    </td>
                    <td>
                      {team.completed_at &&
                        ["RUNNING", "PAUSED"].includes(c.status) && (
                          <Button
                            variant="secondary"
                            disabled={a.busy}
                            onClick={() => {
                              if (confirm(t("reopenConfirm")))
                                a.execute(async () => {
                                  await api(
                                    `/contests/${id}/participants/${team.identity}/reopen`,
                                    {},
                                  );
                                  q.invalidateQueries({
                                    queryKey: ["control", id],
                                  });
                                });
                            }}
                          >
                            {t("reopenParticipation")}
                          </Button>
                        )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t("teams")}</th>
                  <th>{t("organization")}</th>
                  <th>{t("participants")}</th>
                  <th>{t("connection")}</th>
                </tr>
              </thead>
              <tbody>
                {d.teams.map((team: any) => (
                  <tr key={team.identity}>
                    <td>
                      <strong>{team.name}</strong>
                    </td>
                    <td>{team.organization}</td>
                    <td>{team.members.map((m: any) => m.name).join(", ")}</td>
                    <td>{t(team.online ? "online" : "away")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="puzzle-gallery">
            {board.data?.rows.map((row: any) => (
              <PuzzleCollection
                key={`${row.team_id}:${row.user_id}`}
                row={row}
                data={board.data}
              />
            ))}
          </div>
        </>
      )}
      {tab === "problems" && (
        <ProblemStats problems={d.problems} onRejudge={(pid) => rejudge(pid)} />
      )}
      {tab === "messages" && <Messages id={id!} teacher />}
      {tab === "puzzles" && (
        <>
          <div className="row standings-actions">
            <Link className="button secondary" to={`/contests/${id}/puzzles`}>
              {t("puzzleDesk")}
            </Link>
            <Link
              target="_blank"
              className="button secondary"
              to={
                c.public_scoreboard
                  ? `/display/contests/${id}/puzzles`
                  : `/contests/${id}/control`
              }
              onClick={(e) => {
                if (!c.public_scoreboard) {
                  e.preventDefault();
                  setTab("settings");
                }
              }}
            >
              {t("projector")}
            </Link>
          </div>
          <PuzzleDesk id={id!} />
        </>
      )}
      {tab === "replay" && <ReplayReveal id={id!} contest={c} />}
      {tab === "settings" && (
        <div className="control-columns">
          <ContestDetailsForm key={c.id + ":" + c.status} contest={c} />
          <section className="card control-panel">
            <h2>{t("publicBoard")}</h2>
            <label className="check-row">
              <input
                type="checkbox"
                checked={c.practice_enabled}
                onChange={(e) =>
                  a.execute(async () => {
                    await api(
                      `/contests/${id}/practice`,
                      { practice_enabled: e.target.checked },
                      "PATCH",
                    );
                    q.invalidateQueries({ queryKey: ["contest", id] });
                  })
                }
              />
              {t("practiceEnabled")}
            </label>
            <label className="check-row">
              <input
                type="checkbox"
                checked={c.public_scoreboard}
                disabled={a.busy}
                onChange={(e) =>
                  a.execute(async () => {
                    await api(
                      `/contests/${id}/display`,
                      { public_scoreboard: e.target.checked },
                      "PATCH",
                    );
                    q.invalidateQueries({ queryKey: ["contest", id] });
                  })
                }
              />
              {t("publicAccess")}
            </label>
            <p className="muted">{t("publicHint")}</p>
            <h3>{t("languages")}</h3>
            {Object.entries(languageCatalog).map(([lang, info]) => (
              <label className="check-row" key={lang}>
                <input
                  type="checkbox"
                  checked={c.languages.includes(lang)}
                  disabled={
                    a.busy ||
                    ["RUNNING", "PAUSED"].includes(c.status) ||
                    (c.languages.length === 1 && c.languages.includes(lang))
                  }
                  onChange={() =>
                    a.execute(async () => {
                      await api(
                        `/contests/${id}/languages`,
                        {
                          languages: c.languages.includes(lang)
                            ? c.languages.filter((x: string) => x !== lang)
                            : [...c.languages, lang],
                        },
                        "PATCH",
                      );
                      q.invalidateQueries({ queryKey: ["contest", id] });
                    })
                  }
                />
                {info.label}
              </label>
            ))}
            <Field label={t("logo")}>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file)
                    a.execute(async () => {
                      if (file.size > 500000) throw new Error(t("logoHint"));
                      const content = await new Promise<string>(
                        (resolve, reject) => {
                          const r = new FileReader();
                          r.onload = () => resolve(String(r.result));
                          r.onerror = reject;
                          r.readAsDataURL(file);
                        },
                      );
                      await api(`/contests/${id}/logo`, { data: content });
                      q.invalidateQueries({ queryKey: ["contest", id] });
                    });
                }}
              />
            </Field>
            <p className="muted">{t("logoHint")}</p>
            {c.logo_data && (
              <img
                className="contest-logo-preview"
                src={c.logo_data}
                alt={c.title}
              />
            )}
          </section>
          <section className="card control-panel">
            <h2>{t("serverAddress")}</h2>
            <details>
              <summary>{t("networkMode")}</summary>
              <p>{t("networkHint")}</p>
              <a href="/api/v1/network/windows-script" download>
                {t("networkScript")}
              </a>
            </details>
            <Field label={t("serverAddress")}>
              <input
                type="url"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                onBlur={() => {
                  if (validAddress)
                    localStorage.setItem("ca_lan_address", address);
                }}
              />
            </Field>
            <p className="muted">{t("lanHint")}</p>
            {validAddress && (
              <div className="lan-qr">
                <QRCodeSVG value={address} size={180} marginSize={3} />
                <a href={address}>{address}</a>
              </div>
            )}
            <p>
              {t("online")}: {d.teams.filter((x: any) => x.online).length}
            </p>
            <p>
              {t(
                d.judge.judge_available
                  ? "checkingAvailable"
                  : "checkingUnavailable",
              )}
            </p>
          </section>
        </div>
      )}
    </>
  );
}

import { ScoreboardTable } from "./Scoreboard";
function PublicBoard({ data }: { data: any }) {
  const { t } = useTranslation();
  return (
    <>
      {data.frozen && <p className="notice warning">{t("frozen")}</p>}
      <ScoreboardTable data={data} />
    </>
  );
}
function ProblemStats({
  problems,
  onRejudge,
  compact = false,
}: {
  problems: any[];
  onRejudge?: (id: number) => void;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className={`statistics-grid ${compact ? "compact" : ""}`}>
      {problems.map((p) => (
        <article className="problem-stat" key={p.id}>
          <div className="row between">
            <h3>
              {p.letter} · {p.title}
            </h3>
            <strong>{p.solved}</strong>
          </div>
          <progress
            value={p.solve_rate}
            max={100}
            aria-label={t("solveRate")}
          />
          {!compact && (
            <>
              <p>
                {t("attempts")}: {p.attempts} · {t("solveRate")}: {p.solve_rate}
                %
              </p>
              <div className="verdict-counts">
                {Object.entries(p.verdicts).map(([v, n]) => (
                  <span key={v}>
                    {t(v)} <strong>{String(n)}</strong>
                  </span>
                ))}
              </div>
              {p.first_solve && (
                <p>
                  {t("firstSolve")}: {p.first_solve.name} ·{" "}
                  {Math.floor(p.first_solve.elapsed / 60)}′
                </p>
              )}
              <small>
                {t("averageAttempts")}: {p.average_attempts ?? "—"}
              </small>
            </>
          )}
          {onRejudge && (
            <Button variant="ghost" onClick={() => onRejudge(p.id)}>
              {t("rejudgeProblem")}
            </Button>
          )}
        </article>
      ))}
    </div>
  );
}
