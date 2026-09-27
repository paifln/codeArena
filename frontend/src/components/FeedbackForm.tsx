import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { Button, ErrorBox, Field, useAction } from "../ui";
export function FeedbackForm({
  id,
  feedback,
}: {
  id: number;
  feedback: string;
}) {
  const { t } = useTranslation();
  const action = useAction();
  const query = useQueryClient();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const text = new FormData(e.currentTarget).get("feedback");
        action.execute(async () => {
          await api(`/submissions/${id}/feedback`, { feedback: text }, "PATCH");
          await query.invalidateQueries({ queryKey: ["submission", id] });
        });
      }}
    >
      <Field label={t("feedback")}>
        <textarea
          name="feedback"
          rows={4}
          maxLength={5000}
          defaultValue={feedback}
        />
      </Field>
      <ErrorBox error={action.error} />
      <Button disabled={action.busy}>{t("save")}</Button>
    </form>
  );
}
