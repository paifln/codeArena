import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, type User } from "../api";
import { Button, ErrorBox, Field } from "../ui";
export type Options = {
  mode: string;
  scoring: string;
  practice_enabled: boolean;
  teams: { name: string; user_ids: number[] }[];
};
export const defaultOptions: Options = {
  mode: "INDIVIDUAL",
  scoring: "ICPC",
  practice_enabled: false,
  teams: [],
};
export function ContestOptions({
  value,
  onChange,
}: {
  value: Options;
  onChange: (v: Options) => void;
}) {
  const { t } = useTranslation();
  const users = useQuery({
    queryKey: ["/users"],
    queryFn: () => api<User[]>("/users"),
  });
  const update = (change: Partial<Options>) =>
    onChange({ ...value, ...change });
  return (
    <>
      <div className="form-grid">
        <Field label={t("mode")}>
          <select
            value={value.mode}
            onChange={(e) => update({ mode: e.target.value, teams: [] })}
          >
            {["INDIVIDUAL", "TEAM"].map((x) => (
              <option key={x} value={x}>
                {t(x)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("scoring")}>
          <select
            value={value.scoring}
            onChange={(e) => update({ scoring: e.target.value })}
          >
            {["ICPC", "EDUCATIONAL", "PARTIAL"].map((x) => (
              <option key={x} value={x}>
                {t(x)}
              </option>
            ))}
          </select>
        </Field>
      </div>
      {value.scoring === "PARTIAL" && (
        <p className="muted">{t("weightHint")}</p>
      )}
      <label className="check-row">
        <input
          type="checkbox"
          checked={value.practice_enabled}
          onChange={(e) => update({ practice_enabled: e.target.checked })}
        />
        {t("practiceEnabled")}
      </label>
      {value.mode === "TEAM" && (
        <section>
          <h3>{t("teams")}</h3>
          <p className="muted">{t("teamHint")}</p>
          <ErrorBox error={users.error} />
          {value.teams.map((team, i) => (
            <div
              className="card"
              style={{ padding: 16, marginBottom: 12 }}
              key={i}
            >
              <Field label={t("teamName")}>
                <input
                  required
                  maxLength={100}
                  value={team.name}
                  onChange={(e) =>
                    update({
                      teams: value.teams.map((x, j) =>
                        i === j ? { ...x, name: e.target.value } : x,
                      ),
                    })
                  }
                />
              </Field>
              <div className="selection-list">
                {users.data
                  ?.filter((u) => u.role === "STUDENT")
                  .map((u) => (
                    <label key={u.id} className="check-row">
                      <input
                        type="checkbox"
                        checked={team.user_ids.includes(u.id)}
                        disabled={
                          !team.user_ids.includes(u.id) &&
                          (team.user_ids.length >= 3 ||
                            value.teams.some((x) => x.user_ids.includes(u.id)))
                        }
                        onChange={(e) =>
                          update({
                            teams: value.teams.map((x, j) =>
                              j === i
                                ? {
                                    ...x,
                                    user_ids: e.target.checked
                                      ? [...x.user_ids, u.id]
                                      : x.user_ids.filter((id) => id !== u.id),
                                  }
                                : x,
                            ),
                          })
                        }
                      />
                      {u.name} ({u.username})
                    </label>
                  ))}
              </div>
              <Button
                type="button"
                variant="ghost danger"
                onClick={() =>
                  update({ teams: value.teams.filter((_, j) => j !== i) })
                }
              >
                {t("delete")}
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="secondary"
            onClick={() =>
              update({ teams: [...value.teams, { name: "", user_ids: [] }] })
            }
          >
            {t("addTeam")}
          </Button>
        </section>
      )}
    </>
  );
}
