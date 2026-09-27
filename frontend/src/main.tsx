import { Operations } from "./components/Operations";
import {
  ControlCenter,
  PuzzleDeskPage,
} from "./features/contest/ControlCenter";
import { PublicDisplay } from "./features/contest/PublicDisplay";
import { ProfileMenu } from "./components/ProfileMenu";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/jetbrains-mono/400.css";
import { QueryClientProvider, useQuery } from "@tanstack/react-query";
import {
  Activity,
  BookOpen,
  Home,
  Menu,
  Moon,
  Settings,
  Sun,
  Trophy,
  Users,
  WifiOff,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { useTranslation } from "react-i18next";
import {
  BrowserRouter,
  NavLink,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { api, useSession } from "./api";
import { Contest, Submissions } from "./contest";
import { Solver } from "./features/solver/Solver";
import "./i18n";
import { queryClient } from "./lib/queryClient";
import { Contests, Dashboard, Groups, Preferences, Problems } from "./pages";
import "./style.css";
import { Button, ErrorBox, Field, Loading, Logo, useAction } from "./ui";
export function useTheme() {
  const [theme, setTheme] = useState(
    localStorage.getItem("ca_theme") || "system",
  );
  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () =>
      document.documentElement.classList.toggle(
        "dark",
        theme === "dark" || (theme === "system" && media.matches),
      );
    apply();
    media.addEventListener("change", apply);
    localStorage.setItem("ca_theme", theme);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
  return { theme, setTheme };
}
function Auth({ setup, onDone }: { setup: boolean; onDone: () => void }) {
  const { t, i18n } = useTranslation();
  const a = useAction();
  return (
    <main className="auth">
      <section className="auth-story">
        <Logo />
        <div>
          <h1>{t("contests")}</h1>
          <div className="code-art">
            <div className="code-art-top">
              <i />
              <i />
              <i />
              <span>your_next_chapter.py</span>
            </div>
            <pre>
              <span className="code-purple">while</span> curious:
              <br /> learn()
              <br /> build()
              <br /> <span className="code-lime">keep_going()</span>
            </pre>
            <span className="art-chip">{"✓  Accepted"}</span>
          </div>
        </div>
      </section>
      <section className="auth-form">
        <div className="auth-language">
          <select
            aria-label={t("language")}
            value={i18n.language}
            onChange={(e) => {
              i18n.changeLanguage(e.target.value);
              localStorage.setItem("ca_language", e.target.value);
            }}
          >
            <option value="ru">Русский</option>
            <option value="kk">Қазақша</option>
            <option value="en">English</option>
          </select>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            a.execute(async () => {
              await api(
                "/auth/" + (setup ? "setup" : "login"),
                Object.fromEntries(f),
              );
              onDone();
            });
          }}
        >
          <h2>{t(setup ? "setup" : "loginTitle")}</h2>
          <p>{t(setup ? "setupText" : "loginText")}</p>
          {setup && (
            <>
              <Field label={t("organization")}>
                <input
                  name="organization"
                  required
                  maxLength={120}
                  autoComplete="organization"
                />
              </Field>
              <Field label={t("name")}>
                <input
                  name="name"
                  required
                  maxLength={100}
                  autoComplete="name"
                />
              </Field>
            </>
          )}
          <Field label={t("username")}>
            <input
              name="username"
              required
              autoComplete="username"
              autoFocus
              minLength={3}
            />
          </Field>
          <Field label={t("password")}>
            <input
              name="password"
              type="password"
              required
              minLength={setup ? 10 : 1}
              autoComplete={setup ? "new-password" : "current-password"}
              placeholder={setup ? t("passwordHint") : ""}
            />
          </Field>
          <ErrorBox error={a.error} />
          <Button disabled={a.busy} type="submit">
            {t(a.busy ? "loading" : setup ? "createSpace" : "login")}{" "}
            <span>→</span>
          </Button>
          <p className="auth-note">
            {t(setup ? "setupJudge" : "credentialsHint")}
          </p>
        </form>
      </section>
    </main>
  );
}
function Application() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const [menu, setMenu] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const user = useSession((s) => s.user);
  const setUser = useSession((s) => s.setUser);
  const nav = useNavigate();
  const status = useQuery({
    queryKey: ["status"],
    queryFn: () => api("/auth/status"),
    refetchInterval: 15000,
  });
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api("/auth/me"),
    retry: false,
    enabled: !!status.data && !status.data.setup_required,
  });
  useEffect(() => {
    if (me.data) setUser(me.data);
  }, [me.data, setUser]);
  useEffect(() => {
    if (!user) return;
    const beat = () => api("/heartbeat", {}).catch(() => {});
    beat();
    const timer = setInterval(beat, 20000);
    return () => clearInterval(timer);
  }, [user]);
  useEffect(() => {
    const yes = () => setOnline(true),
      no = () => setOnline(false);
    window.addEventListener("online", yes);
    window.addEventListener("offline", no);
    return () => {
      window.removeEventListener("online", yes);
      window.removeEventListener("offline", no);
    };
  }, []);
  if (status.isPending) return <Loading />;
  if (status.error && !status.data)
    return (
      <div className="startup-error">
        <Logo />
        <ErrorBox error={status.error} />
        <Button onClick={() => status.refetch()}>{t("retry")}</Button>
      </div>
    );
  if (!status.data?.setup_required && me.isPending) return <Loading />;
  if (status.data?.setup_required || !user)
    return (
      <Auth
        setup={!!status.data?.setup_required}
        onDone={async () => {
          await queryClient.invalidateQueries({ queryKey: ["status"] });
          await me.refetch();
          nav("/");
        }}
      />
    );
  const teacher = user.role !== "STUDENT";
  const links: Array<[string, typeof Home, string]> = [
    ["/", Home, "home"],
    ["/contests", Trophy, "contests"],
    ...(teacher
      ? [
          ["/problems", BookOpen, "problems"] as [string, typeof Home, string],
          ["/groups", Users, "groups"] as [string, typeof Home, string],
        ]
      : []),
    ...(user.role === "ADMIN"
      ? [
          ["/operations", Activity, "operations"] as [
            string,
            typeof Home,
            string,
          ],
        ]
      : []),
    ["/submissions", Activity, "submissions"],
  ];
  return (
    <div className="app-shell">
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <NavLink to="/" onClick={() => setMenu(false)}>
          <Logo />
        </NavLink>
        <nav>
          {links.map(([path, Icon, key]) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/"}
              onClick={() => setMenu(false)}
            >
              <Icon size={19} />
              {t(key)}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <NavLink className="settings-link" to="/settings">
            <Settings size={18} />
            {t("settings")}
          </NavLink>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="row">
            <button
              className="icon-button mobile-menu"
              onClick={() => setMenu(!menu)}
              aria-label={t("workspace")}
            >
              <Menu size={22} />
            </button>
            <span className="topbar-label">
              <strong>{t(user.role)}</strong>
            </span>
          </div>
          <div className="row">
            <select
              className="language-select"
              value={i18n.language}
              aria-label={t("language")}
              onChange={(e) => {
                i18n.changeLanguage(e.target.value);
                localStorage.setItem("ca_language", e.target.value);
              }}
            >
              <option value="ru">RU</option>
              <option value="kk">KZ</option>
              <option value="en">EN</option>
            </select>
            <button
              className="icon-button"
              aria-label={t("theme")}
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            >
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <ProfileMenu
              user={user}
              onLogout={async () => {
                await api("/auth/logout", {});
                setUser(null);
                queryClient.clear();
                nav("/");
              }}
            />
          </div>
        </header>
        {(!online || status.isError) && (
          <div className="notice warning">
            <WifiOff size={17} />
            {t("offline")}
          </div>
        )}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/contests" element={<Contests />} />
            <Route path="/contests/:id" element={<Contest />} />
            <Route
              path="/contests/:id/problems/:problemId"
              element={<Solver />}
            />
            {teacher && (
              <>
                <Route
                  path="/contests/:id/control"
                  element={<ControlCenter />}
                />
                <Route
                  path="/contests/:id/puzzles"
                  element={<PuzzleDeskPage />}
                />
                <Route path="/problems" element={<Problems />} />
                <Route path="/groups" element={<Groups />} />
              </>
            )}
            {user.role === "ADMIN" && (
              <Route path="/operations" element={<Operations />} />
            )}
            <Route path="/submissions" element={<Submissions />} />
            <Route
              path="/settings"
              element={<Preferences theme={theme} setTheme={setTheme} />}
            />
            <Route path="*" element={<Dashboard />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route
            path="/display/contests/:id/:view"
            element={<PublicDisplay />}
          />
          <Route path="*" element={<Application />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
