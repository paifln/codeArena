import { useQueryClient } from "@tanstack/react-query";
import { PauseCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { Button, ErrorBox, useAction } from "../../ui";
import type { ContestDetail } from "./types";

export function ExecutionNotice({ contest }: { contest: ContestDetail }) {
  const { t } = useTranslation();
  const query = useQueryClient();
  const action = useAction();
  if (contest.execution.allowed) return null;
  const control =
    contest.status === "PAUSED"
      ? "resume"
      : ["DRAFT", "SCHEDULED"].includes(contest.status)
        ? "start"
        : null;
  return (
    <div className="execution-notice" role="status">
      <PauseCircle size={20} />
      <div>
        <strong>{t(contest.execution.reason || "executionLoading")}</strong>
        {contest.can_manage && control && (
          <Button
            type="button"
            variant="secondary"
            disabled={action.busy}
            onClick={() =>
              action.execute(async () => {
                await api(`/contests/${contest.id}/${control}`, {});
                await query.invalidateQueries({
                  queryKey: ["contest", String(contest.id)],
                });
              })
            }
          >
            {t(control)}
          </Button>
        )}
        <ErrorBox error={action.error} />
      </div>
    </div>
  );
}
