import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { api, downloadCSV } from "../../api";
import { Button, ErrorBox, useAction } from "../../ui";

export function TeamsImport({ onTeams }: { onTeams: (teams: any[]) => void }) {
  const { t } = useTranslation();
  const q = useQueryClient();
  const a = useAction();
  const [csv, setCsv] = useState("");
  const [credentials, setCredentials] = useState<any[]>([]);
  return (
    <details className="card import-teams">
      <summary>{t("importTeams")}</summary>
      <p className="muted">{t("csvHint")}</p>
      <input
        aria-label={t("importTeams")}
        type="file"
        accept=".csv,text/csv"
        onChange={async (e) => {
          const f = e.target.files?.[0];
          if (f && f.size <= 100000) setCsv(await f.text());
        }}
      />
      <textarea
        aria-label="CSV"
        rows={4}
        value={csv}
        maxLength={100000}
        onChange={(e) => setCsv(e.target.value)}
        placeholder="team_name,organization,member1,member2,member3"
      />
      <Button
        type="button"
        disabled={a.busy || !csv.trim()}
        onClick={() =>
          a.execute(async () => {
            const r = await api("/teams/prepare", { csv });
            onTeams(r.teams);
            setCredentials(r.credentials);
            setCsv("");
            q.invalidateQueries({ queryKey: ["/users"] });
          })
        }
      >
        {t("prepareTeams")}
      </Button>
      <ErrorBox error={a.error} />
      {credentials.length > 0 && (
        <>
          <p role="status">{t("credentialsCreated")}</p>
          <Button
            type="button"
            variant="secondary"
            onClick={() =>
              downloadCSV("team-credentials.csv", [
                ["team", "member", "username", "password"],
                ...credentials.map((c) => [
                  c.team,
                  c.name,
                  c.username,
                  c.password,
                ]),
              ])
            }
          >
            {t("download")}
          </Button>
        </>
      )}
    </details>
  );
}
