import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { Button, ErrorBox, Modal, useAction } from "../../ui";

export function ParticipationPanel({ contest: c }: { contest: any }) {
  const { t } = useTranslation();
  const q = useQueryClient();
  const a = useAction();
  const [confirm, setConfirm] = useState(false);
  const p = c.participation;
  if (!p || !["RUNNING", "PAUSED", "FINISHED"].includes(c.status)) return null;
  const next = c.problems?.find((x: any) => !p.solved_ids.includes(x.id));
  return (
    <section
      className="card participation-panel"
      aria-label={t("yourProgress")}
    >
      <div>
        <h3>
          {t(
            p.completed_at
              ? "participationComplete"
              : p.solved === p.total
                ? "allSolved"
                : "yourProgress",
          )}
        </h3>
        <p>{t("solvedProgress", { solved: p.solved, total: p.total })}</p>
        <progress
          aria-label={t("yourProgress")}
          max={Math.max(1, p.total)}
          value={p.solved}
        />
        {p.completed_at && <p className="muted">{t("completionSaved")}</p>}
        {p.pending > 0 && (
          <p role="status">{t("waitingForResults", { count: p.pending })}</p>
        )}
      </div>
      <div className="row">
        {!p.completed_at && next && c.status === "RUNNING" && (
          <Link
            className="button secondary"
            to={`/contests/${c.id}/problems/${next.id}`}
          >
            {t("continueSolving")}
          </Link>
        )}
        {!p.completed_at && c.status !== "FINISHED" && (
          <Button
            disabled={a.busy || p.pending > 0}
            onClick={() => setConfirm(true)}
          >
            {t("finishParticipation")}
          </Button>
        )}
        {p.completed_at && (
          <Link className="button secondary" to="/contests">
            {t("backToContests")}
          </Link>
        )}
      </div>
      <ErrorBox error={a.error} />
      <Modal
        open={confirm}
        onClose={() => !a.busy && setConfirm(false)}
        title={t("finishParticipation")}
      >
        <p>{t(p.team ? "completeTeamConfirm" : "completeConfirm")}</p>
        {p.solved < p.total && (
          <p className="notice warning">
            {t("unfinishedConfirm", { count: p.total - p.solved })}
          </p>
        )}
        <ErrorBox error={a.error} />
        <div className="form-actions">
          <Button
            variant="secondary"
            disabled={a.busy}
            onClick={() => setConfirm(false)}
          >
            {t("cancel")}
          </Button>
          <Button
            disabled={a.busy}
            onClick={() =>
              a.execute(async () => {
                await api(`/contests/${c.id}/complete`, {});
                await q.invalidateQueries({
                  queryKey: ["contest", String(c.id)],
                });
                q.invalidateQueries({ queryKey: ["/contests"] });
                setConfirm(false);
              })
            }
          >
            {t("finishParticipation")}
          </Button>
        </div>
      </Modal>
    </section>
  );
}
