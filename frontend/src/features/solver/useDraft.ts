import { useEffect, useRef, useState } from "react";

/** The workspace is keyed by user/contest/problem: drafts never cross routes. */
export function useDraft(key: string) {
  const [initial] = useState(() => {
    try {
      return { code: localStorage.getItem(key) || "", available: true };
    } catch {
      return { code: "", available: false };
    }
  });
  const [code, setCode] = useState(initial.code);
  const [saveState, setSaveState] = useState<
    "saved" | "saving" | "unavailable"
  >(initial.available ? "saved" : "unavailable");
  const latest = useRef(code);
  latest.current = code;
  const persist = () => {
    try {
      localStorage.setItem(key, latest.current);
      return true;
    } catch {
      return false;
    }
  };
  useEffect(() => {
    setSaveState("saving");
    const timer = setTimeout(
      () => setSaveState(persist() ? "saved" : "unavailable"),
      700,
    );
    return () => clearTimeout(timer);
  }, [code, key]);
  useEffect(() => {
    const flush = () => {
      persist();
    };
    window.addEventListener("pagehide", flush);
    window.addEventListener("beforeunload", flush);
    return () => {
      window.removeEventListener("pagehide", flush);
      window.removeEventListener("beforeunload", flush);
      flush();
    };
  }, [key]);
  return { code, setCode, saveState };
}
