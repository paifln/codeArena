import { useEffect, useRef, useState } from "react";
import { ChevronDown, LogOut } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { User } from "../api";
import { ErrorBox, useAction } from "../ui";

export function ProfileMenu({
  user,
  onLogout,
}: {
  user: User;
  onLogout: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const item = useRef<HTMLButtonElement>(null);
  const action = useAction();
  useEffect(() => {
    if (!open) return;
    item.current?.focus();
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  return (
    <div
      className="profile-menu"
      ref={root}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false);
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          setOpen(false);
          trigger.current?.focus();
        }
        if (open && ["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) {
          e.preventDefault();
          item.current?.focus();
        }
      }}
    >
      <button
        className="profile-trigger"
        ref={trigger}
        aria-label={t("profileMenu")}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setOpen(true);
          }
        }}
      >
        <span className="avatar small">{user.name.slice(0, 1)}</span>
        <span className="profile-name">{user.name}</span>
        <ChevronDown size={15} />
      </button>
      {open && (
        <div className="profile-dropdown">
          <div className="profile-summary">
            <strong>{user.name}</strong>
            <small>{t(user.role)}</small>
          </div>
          <div role="menu" aria-label={t("profileMenu")}>
            <button
              ref={item}
              role="menuitem"
              disabled={action.busy}
              onClick={() => action.execute(onLogout)}
            >
              <LogOut size={17} />
              {t("logout")}
            </button>
          </div>
          <ErrorBox error={action.error} />
        </div>
      )}
    </div>
  );
}
