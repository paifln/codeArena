import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { Button, ErrorBox, Field, Modal, useAction } from "../ui";

export type PeopleAction = {
  kind: "group" | "student" | "password";
  id: number;
  name: string;
};
export function PeopleActionDialog({
  target,
  onClose,
}: {
  target: PeopleAction;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const query = useQueryClient();
  const action = useAction();
  const [done, setDone] = useState(false);
  const password = target.kind === "password";
  const label = password
    ? "resetPassword"
    : target.kind === "group"
      ? "deleteGroup"
      : "deleteStudent";
  return (
    <Modal
      open
      onClose={() => {
        if (!action.busy) onClose();
      }}
      title={t(label)}
    >
      <p>
        <strong>{target.name}</strong>
      </p>
      {done ? (
        <>
          <p className="notice success" role="status">
            {t("passwordResetDone")}
          </p>
          <Button onClick={onClose}>{t("close")}</Button>
        </>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const data = new FormData(form);
            action.execute(async () => {
              if (password) {
                if (data.get("password") !== data.get("repeat"))
                  throw new Error(t("passwordsMismatch"));
                await api(`/users/${target.id}/reset-password`, {
                  new_password: data.get("password"),
                });
                form.reset();
                setDone(true);
              } else {
                await api(
                  `/${target.kind === "group" ? "groups" : "users"}/${target.id}`,
                  undefined,
                  "DELETE",
                );
                await query.invalidateQueries();
                onClose();
              }
            });
          }}
        >
          <p className="muted">{t(label + "Hint")}</p>
          {password && (
            <>
              <Field label={t("newPassword")}>
                <input
                  name="password"
                  type="password"
                  minLength={10}
                  maxLength={256}
                  autoComplete="new-password"
                  required
                />
              </Field>
              <Field label={t("repeatPassword")}>
                <input
                  name="repeat"
                  type="password"
                  minLength={10}
                  maxLength={256}
                  autoComplete="new-password"
                  required
                />
              </Field>
              <p className="muted">{t("passwordHint")}</p>
            </>
          )}
          <ErrorBox error={action.error} />
          <div className="form-actions">
            <Button
              type="button"
              variant="secondary"
              disabled={action.busy}
              onClick={onClose}
            >
              {t("cancel")}
            </Button>
            <Button
              type="submit"
              variant={password ? "" : "danger"}
              disabled={action.busy}
            >
              {t(label)}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
