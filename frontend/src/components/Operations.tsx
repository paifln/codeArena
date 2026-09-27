import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { ErrorBox, Heading, Loading } from "../ui";
export function Operations() {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: ["operations"],
    queryFn: () => api("/operations"),
    refetchInterval: 5000,
  });
  if (query.isPending) return <Loading />;
  const data = query.data;
  return (
    <>
      <Heading title={t("operations")} />
      <ErrorBox error={query.error} />
      {data && (
        <>
          {data.alerts.map((key: string) => (
            <p className="notice warning" role="status" key={key}>
              {t("alert_" + key)}
            </p>
          ))}
          <div className="cards-grid">
            {[
              ["pendingJobs", data.pending],
              ["oldestJob", data.oldest_seconds],
              ["systemErrors", data.system_errors_24h],
              ["freeDisk", (data.disk_free_bytes / 1024 ** 3).toFixed(1)],
            ].map(([label, value]) => (
              <section className="card settings-card" key={label}>
                <h3>{t(label)}</h3>
                <strong>{value}</strong>
              </section>
            ))}
          </div>
          <section className="card settings-card section-gap">
            <h3>{t("backup")}</h3>
            <p>
              {t(data.backup?.verified ? "backupVerified" : "backupMissing")}
            </p>
            {data.backup?.time && (
              <p>{new Date(data.backup.time * 1000).toLocaleString()}</p>
            )}

            {data.backup?.verified && data.backup?.file && (
              <p><a href={`/api/v1/operations/backups/${encodeURIComponent(data.backup.file)}`} download>
                {t("downloadBackup")}
              </a></p>
            )}
            {data.backup?.size_bytes != null && (
              <p>{(data.backup.size_bytes / 1024 / 1024).toFixed(2)} MB</p>
            )}
          </section>
        </>
      )}
    </>
  );
}
