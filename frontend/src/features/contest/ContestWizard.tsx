import { languages as languageCatalog } from "../../languages";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { Button, ErrorBox, Field, useAction } from "../../ui";
import {
  ContestOptions,
  defaultOptions,
} from "../../components/ContestOptions";
import { TeamsImport } from "./TeamsImport";

export function ContestWizard({ close }: { close: () => void }) {
  const { t } = useTranslation();
  const nav = useNavigate();
  const q = useQueryClient();
  const a = useAction();
  const [step, setStep] = useState(0);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [start, setStart] = useState(() => {
    const d = new Date(Date.now() + 300000);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  });
  const [duration, setDuration] = useState(180);
  const [options, setOptions] = useState(defaultOptions);
  const [pids, setPids] = useState<number[]>([]);
  const [gids, setGids] = useState<number[]>([]);
  const [uids, setUids] = useState<number[]>([]);
  const [freeze, setFreeze] = useState(60);
  const [penalty, setPenalty] = useState(20);
  const [rules, setRules] = useState("");
  const [languages, setLanguages] = useState(["python3", "cpp20", "java17"]);
  const [publicBoard, setPublicBoard] = useState(false);
  const [dragged, setDragged] = useState<number | null>(null);
  const problems = useQuery({
    queryKey: ["/problems"],
    queryFn: () => api<any[]>("/problems"),
  });
  const groups = useQuery({
    queryKey: ["/groups"],
    queryFn: () => api<any[]>("/groups"),
  });
  const users = useQuery({
    queryKey: ["/users"],
    queryFn: () => api<any[]>("/users"),
  });
  const labels = [
    "general",
    "schedule",
    "problems",
    "teams",
    "rules",
    "languages",
    "review",
  ];
  const toggle = (ids: number[], id: number) =>
    ids.includes(id) ? ids.filter((v) => v !== id) : [...ids, id];
  const move = (id: number, to: number) =>
    setPids((old) => {
      const next = old.filter((v) => v !== id);
      next.splice(Math.max(0, Math.min(to, next.length)), 0, id);
      return next;
    });
  const valid = [
    title.trim().length >= 2,
    !!start &&
      Number.isFinite(new Date(start).getTime()) &&
      duration > 0 &&
      duration <= 10080,
    pids.length > 0,
    options.mode === "TEAM"
      ? options.teams.length > 0 &&
        options.teams.every((team) => team.name.trim() && team.user_ids.length)
      : gids.length + uids.length > 0,
    freeze >= 0 && freeze < duration && penalty >= 0 && penalty <= 120,
    languages.length > 0,
    true,
  ][step];
  return (
    <form
      className="contest-wizard"
      onSubmit={(e) => {
        e.preventDefault();
        if (step < 6) {
          if (valid) setStep(step + 1);
          return;
        }
        a.execute(async () => {
          const c = await api("/contests", {
            ...options,
            title: title.trim(),
            description,
            start_time: new Date(start).toISOString(),
            end_time: new Date(
              new Date(start).getTime() + duration * 60000,
            ).toISOString(),
            problem_ids: pids,
            group_ids: options.mode === "TEAM" ? [] : gids,
            participant_ids: options.mode === "TEAM" ? [] : uids,
            rules,
            penalty_minutes: penalty,
            freeze_minutes: freeze,
            languages,
            public_scoreboard: publicBoard,
          });
          q.invalidateQueries();
          close();
          nav(`/contests/${c.id}/control`);
        });
      }}
    >
      <ol className="wizard-steps">
        {labels.map((label, i) => (
          <li key={label} aria-current={i === step ? "step" : undefined}>
            <span>{i + 1}</span>
            {t(label)}
          </li>
        ))}
      </ol>
      <h2>{t(labels[step])}</h2>
      {step === 0 && (
        <>
          <Field label={t("title")}>
            <input
              autoFocus
              required
              minLength={2}
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </Field>
          <Field label={t("description")}>
            <textarea
              rows={4}
              maxLength={10000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </Field>
        </>
      )}
      {step === 1 && (
        <div className="form-grid">
          <Field label={t("startTime")}>
            <input
              type="datetime-local"
              required
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </Field>
          <Field label={t("durationMinutes")}>
            <input
              type="number"
              min={1}
              max={10080}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            />
          </Field>
        </div>
      )}
      {step === 2 && (
        <>
          <ErrorBox error={problems.error} />
          <div className="selection-list">
            {problems.data?.map((p) => (
              <label key={p.id} className="check-row">
                <input
                  type="checkbox"
                  checked={pids.includes(p.id)}
                  disabled={pids.length >= 26 && !pids.includes(p.id)}
                  onChange={() => setPids(toggle(pids, p.id))}
                />
                {p.title}
              </label>
            ))}
          </div>
          <h3>{t("orderedProblems")}</h3>
          <ol className="ordered-problems">
            {pids.map((id, i) => (
              <li
                key={id}
                draggable
                onDragStart={() => setDragged(id)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (dragged !== null) move(dragged, i);
                  setDragged(null);
                }}
              >
                <span className="problem-letter">
                  {String.fromCharCode(65 + i)}
                </span>
                <strong>
                  {problems.data?.find((p) => p.id === id)?.title}
                </strong>
                <Button
                  type="button"
                  variant="ghost"
                  disabled={i === 0}
                  aria-label={t("moveUp")}
                  onClick={() => move(id, i - 1)}
                >
                  ↑
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  disabled={i === pids.length - 1}
                  aria-label={t("moveDown")}
                  onClick={() => move(id, i + 1)}
                >
                  ↓
                </Button>
              </li>
            ))}
          </ol>
        </>
      )}
      {step === 3 && (
        <>
          <ContestOptions value={options} onChange={setOptions} />
          {options.mode === "TEAM" ? (
            <TeamsImport
              onTeams={(teams) =>
                setOptions({ ...options, teams: [...options.teams, ...teams] })
              }
            />
          ) : (
            <>
              <h3>{t("groups")}</h3>
              <div className="selection-list">
                {groups.data?.map((g) => (
                  <label key={g.id} className="check-row">
                    <input
                      type="checkbox"
                      checked={gids.includes(g.id)}
                      onChange={() => setGids(toggle(gids, g.id))}
                    />
                    {g.name}
                  </label>
                ))}
              </div>
              <details>
                <summary>{t("participants")}</summary>
                <div className="selection-list">
                  {users.data
                    ?.filter((u) => u.role === "STUDENT")
                    .map((u) => (
                      <label key={u.id} className="check-row">
                        <input
                          type="checkbox"
                          checked={uids.includes(u.id)}
                          onChange={() => setUids(toggle(uids, u.id))}
                        />
                        {u.name}
                      </label>
                    ))}
                </div>
              </details>
            </>
          )}
        </>
      )}
      {step === 4 && (
        <>
          <div className="form-grid">
            <Field label={t("wrongPenalty")}>
              <input
                type="number"
                min={0}
                max={120}
                value={penalty}
                onChange={(e) => setPenalty(Number(e.target.value))}
              />
            </Field>
            <Field label={t("freezeMinutes")}>
              <input
                type="number"
                min={0}
                max={Math.min(1440, duration - 1)}
                value={freeze}
                onChange={(e) => setFreeze(Number(e.target.value))}
              />
            </Field>
          </div>
          <Field label={t("rules")}>
            <textarea
              rows={4}
              maxLength={10000}
              value={rules}
              onChange={(e) => setRules(e.target.value)}
            />
          </Field>
          <label className="check-row">
            <input
              type="checkbox"
              checked={publicBoard}
              onChange={(e) => setPublicBoard(e.target.checked)}
            />
            {t("publicAccess")}
          </label>
          <p className="muted">{t("publicHint")}</p>
        </>
      )}
      {step === 5 &&
        Object.keys(languageCatalog).map((lang) => (
          <label key={lang} className="check-row language-option">
            <input
              type="checkbox"
              checked={languages.includes(lang)}
              onChange={() =>
                setLanguages(
                  languages.includes(lang)
                    ? languages.filter((v) => v !== lang)
                    : [...languages, lang],
                )
              }
            />
            {languageCatalog[lang].label}
          </label>
        ))}
      {step === 6 && (
        <dl className="review-grid">
          <dt>{t("title")}</dt>
          <dd>{title}</dd>
          <dt>{t("schedule")}</dt>
          <dd>
            {new Date(start).toLocaleString()} · {duration} min
          </dd>
          <dt>{t("problems")}</dt>
          <dd>
            {pids
              .map(
                (id, i) =>
                  `${String.fromCharCode(65 + i)}. ${problems.data?.find((p) => p.id === id)?.title}`,
              )
              .join(" / ")}
          </dd>
          <dt>{t("teams")}</dt>
          <dd>
            {options.mode === "TEAM"
              ? options.teams.map((team) => team.name).join(", ")
              : `${gids.length} ${t("groups")} · ${uids.length} ${t("participants")}`}
          </dd>
          <dt>{t("scoring")}</dt>
          <dd>
            {t(options.scoring)} · {penalty} min
          </dd>
          <dt>{t("freeze")}</dt>
          <dd>{freeze} min</dd>
          <dt>{t("languages")}</dt>
          <dd>{languages.join(", ")}</dd>
        </dl>
      )}
      <ErrorBox error={a.error} />
      <div className="wizard-footer">
        <Button
          type="button"
          variant="secondary"
          disabled={step === 0 || a.busy}
          onClick={() => setStep(step - 1)}
        >
          {t("previous")}
        </Button>
        <span className="muted">{step + 1} / 7</span>
        <Button disabled={!valid || a.busy}>
          {t(step === 6 ? "newContest" : "next")}
        </Button>
      </div>
    </form>
  );
}
