import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { Button, ErrorBox, Loading, Logo } from "../../ui";
import { ScoreboardTable, PuzzleCollection } from "./Scoreboard";

export function PublicDisplay() {
  const { id, view } = useParams();
  const { t, i18n } = useTranslation();
  const q = useQueryClient();
  const [connected, setConnected] = useState(false);
  const data = useQuery({
    queryKey: ["public-board", id],
    queryFn: () => api(`/public/contests/${id}/scoreboard`),
    refetchInterval: connected ? 30000 : 10000,
    retry: false,
  });
  useEffect(() => {
    let stopped = false;
    let socket: WebSocket;
    let retry: ReturnType<typeof setTimeout>;
    let previous = "";
    const connect = () => {
      if (stopped) return;
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/public/contests/${id}`,
      );
      socket.onopen = () => setConnected(true);
      socket.onmessage = (e) => {
        if (e.data !== previous) {
          previous = e.data;
          q.invalidateQueries({ queryKey: ["public-board", id] });
        }
      };
      socket.onclose = () => {
        setConnected(false);
        if (!stopped) retry = setTimeout(connect, 5000);
      };
      socket.onerror = () => socket.close();
    };
    connect();
    document.documentElement.classList.toggle(
      "dark",
      localStorage.getItem("ca_theme") === "dark",
    );
    return () => {
      stopped = true;
      clearTimeout(retry);
      socket?.close();
    };
  }, [id, q]);
  if (data.isPending) return <Loading />;
  if (data.error)
    return (
      <main className="display-shell">
        <Logo />
        <ErrorBox error={data.error} />
      </main>
    );
  const board = data.data;
  const earned = board.rows.reduce(
    (sum: number, row: any) => sum + row.solved,
    0,
  );
  const latest = board.rows
    .flatMap((row: any) =>
      row.cells
        .filter((cell: any) => cell.solved)
        .map((cell: any) => ({
          name: row.name,
          letter: cell.letter,
          time: cell.solved_at,
        })),
    )
    .sort((a: any, b: any) => b.time - a.time)
    .slice(0, 5);
  return (
    <main className="display-shell">
      <header className="display-header">
        <div>
          <Logo />
          <h1>{board.title}</h1>
        </div>
        <div className="row">
          <span className="live-label">
            <i />
            {t(board.frozen ? "frozen" : board.status)}
          </span>
          <select
            aria-label={t("language")}
            value={i18n.language}
            onChange={(e) => i18n.changeLanguage(e.target.value)}
          >
            <option value="ru">RU</option>
            <option value="kk">KZ</option>
            <option value="en">EN</option>
          </select>
          <Button
            variant="secondary"
            onClick={() => document.documentElement.requestFullscreen?.()}
          >
            {t("projector")}
          </Button>
        </div>
      </header>
      {board.frozen && <p className="notice warning">{t("frozen")}</p>}
      {view === "puzzles" ? (
        <>
          <div className="puzzle-display-total">
            <span>{t("collected")}</span>
            <strong>{earned}</strong>
          </div>
          <div className="puzzle-recent">
            {latest.map((item: any) => (
              <article className="card" key={`${item.name}:${item.letter}`}>
                <strong>{item.name}</strong>
                <span>
                  + {t("puzzles")} {item.letter}
                </span>
              </article>
            ))}
          </div>
          <div className="puzzle-gallery">
            {board.rows.map((row: any) => (
              <PuzzleCollection
                key={`${row.team_id}:${row.user_id}`}
                row={row}
                data={board}
              />
            ))}
          </div>
        </>
      ) : (
        <ScoreboardTable data={board} />
      )}
    </main>
  );
}
