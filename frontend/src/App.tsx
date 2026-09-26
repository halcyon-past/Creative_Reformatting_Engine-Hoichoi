import { NavLink, Route, Routes } from "react-router-dom";
import clsx from "clsx";
import LibraryPage from "./pages/LibraryPage";
import AssetPage from "./pages/AssetPage";
import SpecPage from "./pages/SpecPage";

function Tab({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        clsx(
          "rounded-md px-3 py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors",
          isActive
            ? "bg-ink-700 text-white shadow-xs border border-ink-600/80"
            : "text-slate-400 hover:text-slate-200 hover:bg-ink-800",
        )
      }
    >
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="min-h-screen flex flex-col justify-between bg-ink-900 text-slate-200 selection:bg-accent/30 selection:text-white">
      <div>
        <header className="sticky top-0 z-30 border-b border-ink-600/80 bg-ink-900/90 backdrop-blur-md">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 border border-accent/30 text-accent">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 6h16M4 12h16m-7 6h7"
                  />
                </svg>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-sm font-bold tracking-tight text-white">
                    Creative Reformatting Engine
                  </h1>
                  <span className="rounded bg-accent/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-accent border border-accent/20">
                    hoichoi
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">
                  Subject-aware crop · speaker-tracked reframe · machine-readable compliance
                </p>
              </div>
            </div>

            <nav className="flex items-center gap-1.5">
              <Tab to="/">Library</Tab>
              <Tab to="/spec">Platform Spec</Tab>
            </nav>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-6 py-8">
          <Routes>
            <Route path="/" element={<LibraryPage />} />
            <Route path="/assets/:assetId" element={<AssetPage />} />
            <Route path="/spec" element={<SpecPage />} />
          </Routes>
        </main>
      </div>

      <footer className="border-t border-ink-600/60 bg-ink-900/80 py-4 text-center text-xs text-slate-400">
        Made by{" "}
        <a
          href="https://aritro.cloud"
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-accent hover:underline underline-offset-4 transition-colors"
        >
          Aritro Saha
        </a>
      </footer>
    </div>
  );
}
