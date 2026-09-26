import * as Dialog from "@radix-ui/react-dialog";
import {
  AlertCircle,
  ArrowRight,
  Check,
  Code2,
  LoaderCircle,
  X,
} from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "./api";
export function Button({
  children,
  variant = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: string }) {
  return (
    <button {...props} className={`button ${variant} ${props.className || ""}`}>
      {children}
    </button>
  );
}
export function Logo() {
  return (
    <span className="logo">
      <span className="logo-symbol">
        <Code2 size={23} />
      </span>
      <span>
        Code<span className="logo-arena">Arena</span>
      </span>
    </span>
  );
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
export function Modal({
  title,
  children,
  open,
  onClose,
}: {
  title: string;
  children: ReactNode;
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className="modal">
          <div className="modal-heading">
            <Dialog.Title>{title}</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label={t("close")}>
              <X size={21} />
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">{title}</Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Empty({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-symbol">
        <Code2 size={27} />
      </div>
      <h3>{title}</h3>
      {hint && <p>{hint}</p>}
      {children}
    </div>
  );
}
export function Loading() {
  const { t } = useTranslation();
  return (
    <div className="loading">
      <LoaderCircle className="spin" size={22} />
      {t("loading")}
    </div>
  );
}
export function ErrorBox({ error }: { error: unknown }) {
  const { t } = useTranslation();
  return error ? (
    <div role="alert" className="notice danger">
      <AlertCircle size={18} />
      <span>
        {error instanceof ApiError
          ? t(error.code, { defaultValue: error.message })
          : error instanceof Error
            ? error.message
            : String(error)}
      </span>
    </div>
  ) : null;
}
export function Badge({ value }: { value: string }) {
  const { t } = useTranslation();
  const c = ["ACCEPTED", "RUNNING", "EASY"].includes(value)
    ? "success"
    : [
          "WRONG_ANSWER",
          "HARD",
          "RUNTIME_ERROR",
          "COMPILATION_ERROR",
          "SYSTEM_ERROR",
          "TIME_LIMIT_EXCEEDED",
          "MEMORY_LIMIT_EXCEEDED",
          "OUTPUT_LIMIT_EXCEEDED",
        ].includes(value)
      ? "danger"
      : ["QUEUED", "PAUSED", "MEDIUM", "SCHEDULED"].includes(value)
        ? "warning"
        : "";
  return (
    <span className={`badge ${c}`}>
      {value === "ACCEPTED" ? (
        <Check size={12} />
      ) : (
        <span className="status-dot" />
      )}
      {t(value)}
    </span>
  );
}
export function Heading({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <div className="row">{children}</div>
    </div>
  );
}
export function useAction() {
  const pending = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const execute = async (fn: () => Promise<void>) => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  return { busy, error, execute, setError };
}
export const Arrow = () => <ArrowRight size={17} />;
