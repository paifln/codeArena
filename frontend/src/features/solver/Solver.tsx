import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Clock, Play, Send, Terminal } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { ExecutionNotice } from "./ExecutionNotice";
import { requestId } from "./requestId";
import type {
  ContestDetail,
  ProblemDetail,
  SubmissionKind,
  SubmissionResult,
} from "./types";
import { useDraft } from "./useDraft";
const Editor = lazy(() => import("../../CodeEditor"));

import ReactMarkdown from "react-markdown";
import { api, useSession } from "../../api";
import { Badge, Button, ErrorBox, Field, Loading, useAction } from "../../ui";

import { useContestEvents } from "../../useContestEvents";

import { Timer } from "../../components/ContestTimer";
import { Results } from "../../components/SubmissionResults";
export function Solver() {
  const { id, problemId } = useParams();
  const [language, setLanguage] = useState("python3");
  const user = useSession((s) => s.user);
  return user ? (
    <SolverWorkspace
      key={`${user.id}:${id}:${problemId}:${language}`}
      language={language}
      setLanguage={setLanguage}
    />
  ) : null;
}

function SolverWorkspace({
  language,
  setLanguage,
}: {
  language: string;
  setLanguage: (value: string) => void;
}) {
  const { id, problemId } = useParams();
  useContestEvents(id);
  const { t } = useTranslation();
  const user = useSession((s) => s.user)!;
  const key =
    `ca_draft:${user.id}:${id}:${problemId}` +
    (language === "python3" ? "" : `:${language}`);
  const { code, setCode, saveState } = useDraft(key);
  const [custom, setCustom] = useState("");
  const [useCustom, setUseCustom] = useState(false);
  const [submission, setSubmission] = useState<number | null>(null);
  const [dark, setDark] = useState(
    document.documentElement.classList.contains("dark"),
  );
  const [width, setWidth] = useState(44);
  const a = useAction();
  const contest = useQuery({
    queryKey: ["contest", id],
    queryFn: () => api<ContestDetail>(`/contests/${id}`),
    refetchInterval: 5000,
  });
  const problem = useQuery({
    queryKey: ["problem", problemId, id, contest.data?.status],
    queryFn: () =>
      api<ProblemDetail>(`/problems/${problemId}?contest_id=${id}`),
  });
  const result = useQuery({
    queryKey: ["submission", submission],
    queryFn: () => api<SubmissionResult>(`/submissions/${submission}`),
    enabled: submission !== null,
    refetchInterval: (q) =>
      !q.state.data || ["QUEUED", "RUNNING"].includes(q.state.data.status)
        ? 1200
        : false,
  });
  useEffect(() => {
    const observer = new MutationObserver(() =>
      setDark(document.documentElement.classList.contains("dark")),
    );
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, []);
  const practice =
    contest.data?.status === "FINISHED" && !!contest.data?.practice_enabled;
  const execution = practice
    ? contest.data?.practice_execution
    : contest.data?.execution;
  const judging = ["QUEUED", "RUNNING"].includes(result.data?.status || "");
  const waiting =
    a.busy || judging || (submission !== null && result.isPending);
  const enabled =
    !!execution?.allowed && !contest.isError && !waiting && !!code.trim();
  const retry = useRef<{ signature: string; id: string } | null>(null);
  const submitting = useRef(false);
  const send = (kind: SubmissionKind) => {
    if (!enabled || submitting.current) return;
    submitting.current = true;
    a.execute(async () => {
      try {
        const payload = {
          contest_id: Number(id),
          problem_id: Number(problemId),
          source: code,
          language,
          practice,
          kind,
          ...(kind === "RUN" && useCustom ? { custom_input: custom } : {}),
        };
        const signature = JSON.stringify(payload);
        if (retry.current?.signature !== signature)
          retry.current = { signature, id: requestId() };
        const s = await api<SubmissionResult>("/submissions", {
          ...payload,
          request_id: retry.current.id,
        });
        retry.current = null;
        setSubmission(s.id);
      } finally {
        submitting.current = false;
      }
    });
  };
  const sendRef = useRef(send);
  sendRef.current = send;
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        sendRef.current(e.shiftKey ? "SUBMIT" : "RUN");
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  if (problem.isPending) return <Loading />;
  if (!problem.data) return <ErrorBox error={problem.error} />;
  const p = problem.data;
  return (
    <div className="solver">
      <div className="solver-heading">
        <Link className="back-link" to={`/contests/${id}`}>
          <ArrowLeft size={16} />
          {contest.data?.title || t("back")}
        </Link>
        {contest.data && <Timer contest={contest.data} />}
      </div>
      {practice && <p className="notice success">{t("practiceHint")}</p>}
      <div className="solver-problems">
        {contest.data?.problems?.map((pr: any, i: number) => (
          <Link
            key={pr.id}
            className={String(pr.id) === problemId ? "selected" : ""}
            to={`/contests/${id}/problems/${pr.id}`}
          >
            {pr.letter || String.fromCharCode(65 + i)} <span>{pr.title}</span>
          </Link>
        ))}
      </div>
      <ErrorBox error={contest.error} />
      {contest.data && (
        <ExecutionNotice
          contest={{
            ...contest.data,
            execution: execution || contest.data.execution,
          }}
        />
      )}
      <div
        className="solver-grid"
        style={{
          gridTemplateColumns: `minmax(260px,${width}fr) 8px minmax(300px,${100 - width}fr)`,
        }}
      >
        <section className="card statement">
          <div className="statement-heading">
            <span className="eyebrow">{t("tasks")}</span>
            <h1>{p.title}</h1>
            <div className="row">
              <Badge value={p.difficulty} />
              <span className="muted">
                <Clock size={13} /> {p.time_limit}s · {p.mem_limit} MB
              </span>
            </div>
          </div>
          {p.editorial && (
            <details className="markdown">
              <summary>{t("editorial")}</summary>
              <ReactMarkdown>{p.editorial}</ReactMarkdown>
            </details>
          )}
          <div className="markdown">
            <ReactMarkdown>{p.description}</ReactMarkdown>
            <h3>{t("input")}</h3>
            <ReactMarkdown>{p.input_fmt}</ReactMarkdown>
            <h3>{t("output")}</h3>
            <ReactMarkdown>{p.output_fmt}</ReactMarkdown>
          </div>
          {(p.samples || []).map((s: any, i: number) => (
            <div className="sample" key={i}>
              <h3>
                {t("sample")} {i + 1}
              </h3>
              <div className="sample-block">
                <span>{t("input")}</span>
                <pre>{s.input_data}</pre>
              </div>
              <div className="sample-block">
                <span>{t("output")}</span>
                <pre>{s.expected}</pre>
              </div>
            </div>
          ))}
        </section>
        <div
          className="resize-handle"
          role="separator"
          aria-label={t("code")}
          aria-orientation="vertical"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") setWidth(Math.max(25, width - 2));
            if (e.key === "ArrowRight") setWidth(Math.min(65, width + 2));
          }}
          onPointerDown={(e) => {
            const parent = e.currentTarget.parentElement!;
            e.currentTarget.setPointerCapture(e.pointerId);
            const move = (ev: PointerEvent) => {
              const r = parent.getBoundingClientRect();
              setWidth(
                Math.max(
                  25,
                  Math.min(65, ((ev.clientX - r.left) / r.width) * 100),
                ),
              );
            };
            const up = () => {
              window.removeEventListener("pointermove", move);
              window.removeEventListener("pointerup", up);
            };
            window.addEventListener("pointermove", move);
            window.addEventListener("pointerup", up);
          }}
        />
        <section className="card editor-panel">
          <div className="editor-header">
            <span>
              <Terminal size={16} />{" "}
              {language === "java17"
                ? "Main.java"
                : language === "cpp20"
                  ? "main.cpp"
                  : "main.py"}
            </span>
            <select
              aria-label={t("languageVersion")}
              value={language}
              disabled={waiting}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="python3">Python 3.12</option>
              <option value="cpp20">C++20 (GCC 12)</option>
              <option value="java17">Java 17</option>
            </select>
          </div>
          <Suspense fallback={<Loading />}>
            <Editor
              height="420px"
              language={
                language === "python3"
                  ? "python"
                  : language === "cpp20"
                    ? "cpp"
                    : "java"
              }
              theme={dark ? "vs-dark" : "light"}
              value={code}
              onChange={(value) => setCode(value || "")}
              options={{
                fontFamily: "JetBrains Mono",
                fontSize: 14,
                minimap: { enabled: false },
                padding: { top: 20 },
                scrollBeyondLastLine: false,
                automaticLayout: true,
                tabSize: 4,
                wordWrap: "on",
                ariaLabel: t("code"),
              }}
              onMount={(editor, monaco) => {
                editor.addCommand(
                  monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
                  () => sendRef.current("RUN"),
                );
                editor.addCommand(
                  monaco.KeyMod.CtrlCmd |
                    monaco.KeyMod.Shift |
                    monaco.KeyCode.Enter,
                  () => sendRef.current("SUBMIT"),
                );
              }}
            />
          </Suspense>
          <div className="editor-status">
            <span>
              {t(
                saveState === "saved"
                  ? "draftSaved"
                  : saveState === "saving"
                    ? "draftSaving"
                    : "draftUnavailable",
              )}
            </span>
            <span>UTF-8</span>
          </div>
          <div className="editor-console">
            <p className="muted">{t("runNoPenalty")}</p>
            {language === "java17" && <p className="muted">{t("javaHint")}</p>}
            <label className="check-row">
              <input
                type="checkbox"
                checked={useCustom}
                onChange={(e) => setUseCustom(e.target.checked)}
              />
              {t("customInput")}
            </label>
            {useCustom && (
              <Field label={t("customInput")}>
                <textarea
                  rows={3}
                  className="mono"
                  value={custom}
                  onChange={(e) => setCustom(e.target.value)}
                  maxLength={65536}
                />
              </Field>
            )}
            <p className="submission-hint" role="status" id="submission-hint">
              {t(
                waiting
                  ? "judgingHint"
                  : !execution?.allowed
                    ? execution?.reason || "executionLoading"
                    : !code.trim()
                      ? "emptyCodeHint"
                      : "readyToSubmit",
              )}
            </p>
            <div className="editor-actions" aria-describedby="submission-hint">
              <Button
                variant="secondary"
                disabled={!enabled}
                onClick={() => send("RUN")}
              >
                <Play size={15} />
                {t("run")}
              </Button>
              <Button disabled={!enabled} onClick={() => send("SUBMIT")}>
                <Send size={15} />
                {t(judging ? "loading" : "submit")}
              </Button>
            </div>
            <small className="muted shortcut-hint">{t("sourceHint")}</small>
            <ErrorBox error={a.error || result.error} />
            {result.data && <Results result={result.data} />}
          </div>
        </section>
      </div>
    </div>
  );
}
