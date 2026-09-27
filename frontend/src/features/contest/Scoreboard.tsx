import { useLayoutEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Puzzle, Snowflake, Star } from "lucide-react";

export function ScoreboardTable({ data }: { data: any }) {
  const { t } = useTranslation();
  const table = useRef<HTMLTableElement>(null);
  const positions = useRef(new Map<string, number>());
  useLayoutEffect(() => {
    const next = new Map<string, number>();
    table.current
      ?.querySelectorAll<HTMLTableRowElement>("tbody tr")
      .forEach((row) => {
        const key = row.dataset.identity!;
        const top = row.getBoundingClientRect().top;
        next.set(key, top);
        const prior = positions.current.get(key);
        if (
          prior !== undefined &&
          prior !== top &&
          row.animate &&
          !matchMedia("(prefers-reduced-motion: reduce)").matches
        )
          row.animate(
            [
              { transform: `translateY(${prior - top}px)` },
              { transform: "translateY(0)" },
            ],
            { duration: 450, easing: "ease-out" },
          );
      });
    positions.current = next;
  }, [data]);
  return (
    <div className="card table-wrap">
      <table ref={table} className="scoreboard professional-board">
        <thead>
          <tr>
            <th>#</th>
            <th>{t("teams")}</th>
            {data.problems.map((p: any, i: number) => (
              <th key={p.id} title={p.title}>
                <span className={`puzzle-dot puzzle-color-${i % 6}`} />
                {p.letter}
              </th>
            ))}
            <th>{t("solved")}</th>
            <th>{t(data.scoring === "PARTIAL" ? "points" : "penalty")}</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row: any) => (
            <tr
              key={`${row.team_id}:${row.user_id}`}
              data-identity={`${row.team_id}:${row.user_id}`}
            >
              <td>
                <span className={`rank rank-${row.rank}`}>{row.rank}</span>
              </td>
              <td>
                <strong>{row.name}</strong>
                {row.organization && (
                  <small className="block muted">{row.organization}</small>
                )}
              </td>
              {row.cells.map((cell: any, i: number) => (
                <td
                  key={cell.problem_id}
                  title={
                    cell.solved
                      ? t("penaltyBreakdown", {
                          time: cell.time_minutes,
                          penalty: cell.penalty_minutes,
                          total: cell.penalty,
                        })
                      : undefined
                  }
                >
                  <span
                    className={`score-cell puzzle-color-${i % 6} ${cell.solved ? "solved" : cell.attempts ? "attempted" : ""} ${cell.first_solve ? "first-solve" : ""}`}
                  >
                    {cell.solved && <Puzzle size={12} aria-hidden />}
                    {cell.first_solve && (
                      <Star size={12} aria-label={t("firstSolve")} />
                    )}
                    {data.scoring === "PARTIAL"
                      ? cell.score
                      : cell.solved
                        ? `+${cell.attempts || ""}`
                        : cell.attempts
                          ? `-${cell.attempts}`
                          : "·"}
                    {cell.pending > 0 && (
                      <small>
                        <Snowflake size={11} /> {cell.pending}
                      </small>
                    )}
                    {cell.solved && data.scoring !== "PARTIAL" && (
                      <small>{cell.minutes}′</small>
                    )}
                  </span>
                </td>
              ))}
              <td className="mono">
                <strong>{row.solved}</strong>
              </td>
              <td
                className="mono"
                title={`${t("lastAccepted")}: ${Math.floor(row.last_accepted / 60)}′`}
              >
                {data.scoring === "PARTIAL" ? row.score : row.penalty}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PuzzleCollection({ row, data }: { row: any; data: any }) {
  const { t } = useTranslation();
  const count = data.problems.length;
  const columns = Math.ceil(Math.sqrt(count));
  const rows = Math.ceil(count / columns);
  return (
    <section
      className={`card puzzle-collection ${row.solved === count && count ? "complete" : ""}`}
    >
      <div className="row between">
        <h3>{row.name}</h3>
        <span className="mono">
          {row.solved}/{count}
        </span>
      </div>
      <div
        className="puzzle-grid"
        style={{ gridTemplateColumns: `repeat(${columns},1fr)` }}
      >
        {row.cells.map((cell: any, i: number) => (
          <div
            key={cell.problem_id}
            className={`puzzle-piece puzzle-color-${i % 6} ${cell.solved ? "earned" : ""}`}
            title={`${cell.letter}: ${cell.solved ? t("ACCEPTED") : t("waiting")}`}
            style={
              cell.solved && data.logo_data
                ? {
                    backgroundImage: `url(${data.logo_data})`,
                    backgroundSize: `${columns * 100}% ${rows * 100}%`,
                    backgroundPosition: `${columns === 1 ? 0 : ((i % columns) / (columns - 1)) * 100}% ${rows === 1 ? 0 : (Math.floor(i / columns) / (rows - 1)) * 100}%`,
                  }
                : undefined
            }
          >
            <span>{cell.letter}</span>
            {!data.logo_data && cell.solved && <Puzzle size={20} />}
          </div>
        ))}
      </div>
      <small className="muted">
        {row.solved === count && count ? t("puzzleComplete") : t("collected")}
      </small>
    </section>
  );
}
