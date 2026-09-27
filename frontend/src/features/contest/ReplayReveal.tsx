import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { Button, ErrorBox, useAction } from "../../ui";
import { ScoreboardTable } from "./Scoreboard";

export function ReplayReveal({ id, contest }: { id: string; contest: any }) {
  const { t } = useTranslation();
  const q = useQueryClient();
  const a = useAction();
  const [mode, setMode] = useState("replay");
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(10);
  const [auto, setAuto] = useState(false);
  const [interval, setIntervalMs] = useState(2500);
  const [last, setLast] = useState<any>(null);
  const [done, setDone] = useState(false);
  const plannedDuration = Math.max(
    0,
    (new Date(contest.end_time).getTime() -
      new Date(contest.start_time).getTime()) /
      1000,
  );
  const replay = useQuery({
    queryKey: ["replay", id, Math.floor(elapsed)],
    queryFn: () => api(`/contests/${id}/replay?elapsed=${Math.floor(elapsed)}`),
    enabled: contest.status === "FINISHED" && mode === "replay",
  });
  const duration = replay.data?.duration ?? plannedDuration;
  const publicBoard = useQuery({
    queryKey: ["public-board", id],
    queryFn: () => api(`/contests/${id}/public-scoreboard`),
    enabled: mode === "reveal",
  });
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(
      () =>
        setElapsed((v) => {
          const next = Math.min(duration, v + speed);
          if (next >= duration) setPlaying(false);
          return next;
        }),
      1000,
    );
    return () => clearInterval(timer);
  }, [playing, speed, duration]);
  const next = () =>
    a.execute(async () => {
      try {
        const result = await api(`/contests/${id}/reveal`, {});
        setLast(result.revealed);
        setDone(result.done);
        if (result.done) setAuto(false);
        q.setQueryData(["public-board", id], result.board);
        q.invalidateQueries({ queryKey: ["control", id] });
      } catch (e) {
        setAuto(false);
        throw e;
      }
    });
  useEffect(() => {
    if (!auto || a.busy) return;
    const timer = setTimeout(next, interval);
    return () => clearTimeout(timer);
  }, [auto, a.busy, interval, last]);
  if (contest.status !== "FINISHED")
    return <p className="notice">{t("replayHint")}</p>;
  return (
    <section>
      <div className="tabs">
        <button
          className={mode === "replay" ? "selected" : ""}
          onClick={() => {
            setMode("replay");
            setAuto(false);
          }}
        >
          {t("replay")}
        </button>
        <button
          className={mode === "reveal" ? "selected" : ""}
          onClick={() => {
            setMode("reveal");
            setPlaying(false);
          }}
        >
          {t("reveal")}
        </button>
      </div>
      {mode === "replay" ? (
        <>
          <div className="replay-controls">
            <Button onClick={() => setPlaying(!playing)}>
              {t(playing ? "pause" : "play")}
            </Button>
            <select
              aria-label={t("replay")}
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
            >
              {[1, 5, 10, 50].map((v) => (
                <option key={v} value={v}>
                  {v}×
                </option>
              ))}
            </select>
            <input
              aria-label={t("timeline")}
              type="range"
              min={0}
              max={duration}
              value={elapsed}
              onChange={(e) => {
                setPlaying(false);
                setElapsed(Number(e.target.value));
              }}
            />
            <span className="mono">
              {Math.floor(elapsed / 60)}:
              {String(Math.floor(elapsed % 60)).padStart(2, "0")}
            </span>
          </div>
          <ErrorBox error={replay.error} />
          {replay.data && <ScoreboardTable data={replay.data.board} />}
        </>
      ) : (
        <>
          <div className="replay-controls">
            <Button disabled={a.busy || done || !contest.frozen} onClick={next}>
              {t("nextReveal")}
            </Button>
            <Button
              variant="secondary"
              disabled={done || !contest.frozen}
              onClick={() => setAuto(!auto)}
            >
              {t(auto ? "pause" : "autoReveal")}
            </Button>
            <select
              aria-label={t("reveal")}
              value={interval}
              onChange={(e) => setIntervalMs(Number(e.target.value))}
            >
              <option value={5000}>0.5×</option>
              <option value={2500}>1×</option>
              <option value={1200}>2×</option>
            </select>
          </div>
          <ErrorBox error={a.error || publicBoard.error} />
          {last && (
            <div
              className="reveal-card"
              role="status"
              key={`${last.name}:${last.letter}`}
            >
              <strong>{last.name}</strong>
              <span>
                {t("problems")} {last.letter}
              </span>
            </div>
          )}
          {done && <p>{t("revealComplete")}</p>}
          {publicBoard.data && <ScoreboardTable data={publicBoard.data} />}
        </>
      )}
    </section>
  );
}
