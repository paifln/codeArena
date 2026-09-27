import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { Button, ErrorBox, useAction } from "../../ui";

export function ProblemDocuments({
  problemId,
  documents = [],
  contestId,
  editable = false,
}: {
  problemId: number;
  documents?: any[];
  contestId?: string;
  editable?: boolean;
}) {
  const { t } = useTranslation();
  const [rows, setRows] = useState(documents);
  const a = useAction();
  return (
    <section className="problem-documents">
      <h3>{t("documents")}</h3>
      {rows.map((d) => (
        <div className="row between" key={d.id}>
          <a
            href={`/api/v1/problems/${problemId}/documents/${d.id}${contestId ? `?contest_id=${contestId}` : ""}`}
            download
          >
            {d.name} · {Math.ceil(d.size / 1024)} KB
          </a>
          {editable && (
            <Button
              type="button"
              variant="ghost"
              disabled={a.busy}
              onClick={() =>
                a.execute(async () => {
                  await api(
                    `/problems/${problemId}/documents/${d.id}`,
                    undefined,
                    "DELETE",
                  );
                  setRows(rows.filter((x) => x.id !== d.id));
                })
              }
            >
              {t("delete")}
            </Button>
          )}
        </div>
      ))}
      {editable && (
        <>
          <p className="muted">{t("documentsHint")}</p>
          <input
            aria-label={t("documents")}
            type="file"
            accept=".pdf,.docx"
            disabled={a.busy || rows.length >= 3}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file)
                a.execute(async () => {
                  if (file.size > 5 * 1024 * 1024)
                    throw new Error(t("documentsHint"));
                  const body = new FormData();
                  body.append("file", file);
                  const d = await api(`/problems/${problemId}/documents`, body);
                  setRows([...rows, d]);
                });
            }}
          />
        </>
      )}
      <ErrorBox error={a.error} />
    </section>
  );
}

export function ImportProblem({
  onImported,
}: {
  onImported: (value: any) => void;
}) {
  const { t } = useTranslation();
  const a = useAction();
  const [url, setUrl] = useState("");
  const [html, setHtml] = useState<string>();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        a.execute(async () =>
          onImported(await api("/problems/import-url", { url, html })),
        );
      }}
    >
      <label>
        {t("sourceUrl")}
        <input
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://codeforces.com/problemset/problem/4/A"
        />
      </label>
      <p className="muted">Codeforces · AtCoder · CSES</p>
      <label>
        {t("savedHtml")}
        <input
          type="file"
          accept=".html,.htm"
          onChange={(e) => {
            const file = e.target.files?.[0];
            a.execute(async () => {
              if (!file) {
                setHtml(undefined);
                return;
              }
              if (file.size > 2_000_000) throw new Error(t("htmlTooLarge"));
              setHtml(await file.text());
            });
          }}
        />
      </label>
      <p className="notice warning">{t("importReview")}</p>
      <ErrorBox error={a.error} />
      <Button disabled={a.busy}>{t("preview")}</Button>
    </form>
  );
}
