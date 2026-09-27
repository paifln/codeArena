import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { Button, ErrorBox, Field, useAction } from "../../ui";
const localDate = (value: string) => {
  const d = new Date(value);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};
export function ContestDetailsForm({ contest: c }: { contest: any }) {
  const { t } = useTranslation();
  const a = useAction();
  const q = useQueryClient();
  const scheduled = ["DRAFT", "SCHEDULED"].includes(c.status);
  return (
    <form
      className="card control-panel"
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        a.execute(async () => {
          await api(
            `/contests/${c.id}/details`,
            {
              title: f.get("title"),
              description: f.get("description"),
              rules: f.get("rules"),
              ...(scheduled
                ? {
                    start_time: new Date(String(f.get("start"))).toISOString(),
                    end_time: new Date(String(f.get("end"))).toISOString(),
                  }
                : {}),
            },
            "PATCH",
          );
          q.invalidateQueries({ queryKey: ["contest", String(c.id)] });
          q.invalidateQueries({ queryKey: ["/contests"] });
        });
      }}
    >
      <h2>{t("contestDetails")}</h2>
      <Field label={t("title")}>
        <input
          name="title"
          defaultValue={c.title}
          required
          minLength={2}
          maxLength={200}
        />
      </Field>
      <Field label={t("description")}>
        <textarea
          name="description"
          defaultValue={c.description}
          maxLength={10000}
        />
      </Field>
      <Field label={t("rules")}>
        <textarea name="rules" defaultValue={c.rules} maxLength={10000} />
      </Field>
      {scheduled && (
        <div className="form-grid">
          <Field label={t("startTime")}>
            <input
              name="start"
              type="datetime-local"
              required
              defaultValue={localDate(c.start_time)}
            />
          </Field>
          <Field label={t("endTime")}>
            <input
              name="end"
              type="datetime-local"
              required
              defaultValue={localDate(c.end_time)}
            />
          </Field>
        </div>
      )}
      <ErrorBox error={a.error} />
      <Button disabled={a.busy}>{t("save")}</Button>
    </form>
  );
}
