import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { api } from "../../api";
import { Button, ErrorBox, Field, useAction } from "../../ui";
import { ProblemDocuments } from "../contest/ProblemDocuments";
export function ProblemForm({
  close,
  existing,
}: {
  close: () => void;
  existing?: any;
}) {
  const { t } = useTranslation();
  const a = useAction();
  const q = useQueryClient();
  const [tests, setTests] = useState<any[]>(
    existing?.tests || [
      { input_data: "", expected: "", is_sample: true },
      { input_data: "", expected: "", is_sample: false },
    ],
  );
  const [desc, setDesc] = useState(existing?.description || "");
  const [createdId, setCreatedId] = useState<number>();
  const [uploads, setUploads] = useState<File[]>([]);
  const effectiveId = existing?.id || createdId;
  const [preview, setPreview] = useState(false);
  const [rejudgeMode, setRejudgeMode] = useState("none");
  const usage = useQuery({
    queryKey: ["problem-usage", existing?.id],
    queryFn: () => api(`/problems/${existing.id}/usage`),
    enabled: !!existing?.id,
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        a.execute(async () => {
          const saved = await api(
            effectiveId ? `/problems/${effectiveId}` : "/problems",
            {
              title: f.get("title"),
              description: desc,
              constraints: existing?.constraints || "",
              translations: existing?.translations || {},
              editorial: f.get("editorial"),
              input_fmt: f.get("input"),
              output_fmt: f.get("output"),
              difficulty: f.get("difficulty"),
              time_limit: Number(f.get("time")),
              mem_limit: Number(f.get("memory")),
              tags: String(f.get("tags"))
                .split(",")
                .map((v) => v.trim())
                .filter(Boolean),
              tests,
            },
            effectiveId ? "PATCH" : "POST",
          );
          setCreatedId(saved.id);
          for (const file of uploads) {
            const body = new FormData();
            body.append("file", file);
            await api(`/problems/${saved.id}/documents`, body);
            setUploads((current) => current.filter((x) => x !== file));
          }
          if (existing?.id && rejudgeMode !== "none")
            for (const contest of usage.data?.contests || [])
              await api(`/contests/${contest.id}/rejudge`, {
                problem_id: existing.id,
                affected_only: rejudgeMode === "affected",
              });
          q.invalidateQueries({ queryKey: ["/problems"] });
          close();
        });
      }}
    >
      {usage.data?.count > 0 && (
        <div className="notice warning">
          <p>{t("existingSubmissions", { count: usage.data.count })}</p>
          <select
            aria-label={t("rejudge")}
            value={rejudgeMode}
            onChange={(e) => setRejudgeMode(e.target.value)}
          >
            <option value="none">{t("noRejudge")}</option>
            <option value="affected">{t("rejudgeAffected")}</option>
            <option value="all">{t("rejudgeProblem")}</option>
          </select>
        </div>
      )}
      <Field label={t("title")}>
        <input
          name="title"
          defaultValue={existing?.title}
          required
          maxLength={180}
        />
      </Field>
      <div className="row between">
        <label>{t("description")}</label>
        <Button
          type="button"
          variant="ghost"
          onClick={() => setPreview(!preview)}
        >
          {t(preview ? "edit" : "preview")}
        </Button>
      </div>
      {preview ? (
        <div className="markdown preview">
          <ReactMarkdown>{desc}</ReactMarkdown>
        </div>
      ) : (
        <textarea
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          rows={7}
          minLength={10}
          required
        />
      )}
      <div className="form-grid">
        <Field label={t("input")}>
          <textarea name="input" defaultValue={existing?.input_fmt} rows={3} />
        </Field>
        <Field label={t("output")}>
          <textarea
            name="output"
            defaultValue={existing?.output_fmt}
            rows={3}
          />
        </Field>
      </div>
      {existing?.review_required && (
        <p className="notice warning">{t("importReview")}</p>
      )}
      {existing?.id ? (
        <ProblemDocuments
          key={existing.id}
          problemId={existing.id}
          documents={existing.documents}
          editable
        />
      ) : (
        <Field label={t("documents")}>
          <input
            type="file"
            multiple
            accept=".pdf,.docx"
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              a.execute(async () => {
                if (
                  files.length > 3 ||
                  files.some((f) => f.size > 5 * 1024 * 1024)
                )
                  throw new Error(t("documentsHint"));
                setUploads(files);
              });
            }}
          />
          <p className="muted">{t("documentsHint")}</p>
          {uploads.map((file) => (
            <p key={file.name}>{file.name}</p>
          ))}
        </Field>
      )}
      <Field label={t("editorial")}>
        <textarea
          name="editorial"
          rows={5}
          maxLength={30000}
          defaultValue={existing?.editorial || ""}
        />
      </Field>
      <p className="muted">{t("editorialHint")}</p>
      <div className="form-grid three">
        <Field label={t("difficulty")}>
          <select
            name="difficulty"
            defaultValue={existing?.difficulty || "EASY"}
          >
            {["EASY", "MEDIUM", "HARD"].map((x) => (
              <option value={x} key={x}>
                {t(x)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("timeLimit")}>
          <input
            name="time"
            type="number"
            min="0.1"
            max="10"
            step="0.1"
            defaultValue={existing?.time_limit || 2}
          />
        </Field>
        <Field label={t("memoryLimit")}>
          <input
            name="memory"
            type="number"
            min="32"
            max="512"
            defaultValue={existing?.mem_limit || 128}
          />
        </Field>
      </div>
      <Field label={t("tags")}>
        <input name="tags" defaultValue={existing?.tags?.join(", ")} />
      </Field>
      <div className="section-heading">
        <h3>{t("tests")}</h3>
        <label className="button ghost file-upload">
          {t("importTests")}
          <input
            type="file"
            accept="application/json,.json"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file)
                try {
                  const rows = JSON.parse(await file.text());
                  if (
                    !Array.isArray(rows) ||
                    !rows.every(
                      (x) =>
                        typeof x.input_data === "string" &&
                        typeof x.expected === "string" &&
                        typeof x.is_sample === "boolean",
                    )
                  )
                    throw new Error(t("error"));
                  setTests(rows);
                } catch (err) {
                  a.setError(err);
                }
            }}
          />
        </label>
      </div>
      <p className="muted">{t("testHint")}</p>
      {tests.map((test, i) => (
        <div className="test-editor" key={i}>
          <div className="row between">
            <label className="check-row">
              <input
                type="checkbox"
                checked={test.is_sample}
                onChange={(e) =>
                  setTests(
                    tests.map((x, j) =>
                      i === j ? { ...x, is_sample: e.target.checked } : x,
                    ),
                  )
                }
              />
              {t(test.is_sample ? "sample" : "hidden")} #{i + 1}
            </label>
            <button
              className="icon-button"
              type="button"
              aria-label={t("remove")}
              onClick={() => setTests(tests.filter((_, j) => j !== i))}
            >
              <Trash2 size={16} />
            </button>
          </div>
          <Field label={t("weight")}>
            <input
              type="number"
              min={0}
              max={100}
              value={test.weight ?? 1}
              onChange={(e) =>
                setTests(
                  tests.map((x, j) =>
                    i === j ? { ...x, weight: Number(e.target.value) } : x,
                  ),
                )
              }
            />
          </Field>
          <div className="form-grid">
            {["input_data", "expected"].map((key) => (
              <Field
                key={key}
                label={t(key === "input_data" ? "input" : "output")}
              >
                <textarea
                  className="mono"
                  rows={3}
                  value={test[key]}
                  onChange={(e) =>
                    setTests(
                      tests.map((x, j) =>
                        i === j ? { ...x, [key]: e.target.value } : x,
                      ),
                    )
                  }
                />
              </Field>
            ))}
          </div>
        </div>
      ))}
      <Button
        type="button"
        variant="secondary"
        onClick={() =>
          setTests([
            ...tests,
            { input_data: "", expected: "", is_sample: false },
          ])
        }
      >
        <Plus size={15} />
        {t("addTest")}
      </Button>
      <ErrorBox error={a.error} />
      <div className="form-actions">
        <Button type="button" variant="secondary" onClick={close}>
          {t("cancel")}
        </Button>
        <Button
          disabled={
            a.busy || !tests.some((test) => test.is_sample) || desc.length < 10
          }
        >
          {t("save")}
        </Button>
      </div>
    </form>
  );
}
