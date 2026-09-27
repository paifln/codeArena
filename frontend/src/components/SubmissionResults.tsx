import { useTranslation } from "react-i18next";
import { Badge } from "../ui";
export function Results({ result }: { result: any }) {
  const { t } = useTranslation();
  return (
    <div className="result-area" aria-live="polite">
      <Badge value={result.status} />
      {result.is_practice && <span className="badge">{t("practice")}</span>}
      {result.kind !== "RUN" && result.score != null && (
        <p>
          {t("points")}: {result.score}/100
        </p>
      )}
      {result.feedback && (
        <section className="notice">
          <strong>{t("feedback")}</strong>
          <p style={{ whiteSpace: "pre-wrap" }}>{result.feedback}</p>
        </section>
      )}
      {result.message && <pre>{result.message}</pre>}
      {result.error && <pre>{result.error}</pre>}
      {(result.tests || result.results || []).map((r: any, i: number) => (
        <div className="test-result" key={i}>
          <div className="row between">
            <strong>#{i + 1}</strong>
            <Badge value={r.status || r.verdict || result.status} />
            <span className="muted">{r.time_ms ?? 0} ms</span>
          </div>
          {r.stdout !== undefined && (
            <>
              <small>{t("output")}</small>
              <pre>{r.stdout || "∅"}</pre>
            </>
          )}
          {r.output !== undefined && <pre>{r.output || "∅"}</pre>}
          {r.stderr && <pre className="error-output">{r.stderr}</pre>}
        </div>
      ))}
    </div>
  );
}
