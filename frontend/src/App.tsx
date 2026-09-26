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
          "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
          isActive ? "bg-ink-700 text-white" : "text-slate-400 hover:text-slate-200",
        )
      }
    >
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-ink-600 bg-ink-900/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
          <div>
            <h1 className="text-sm font-semibold tracking-tight text-white">
              Creative Reformatting Engine
            </h1>
            <p className="text-xs text-slate-500">
              subject-aware crop · speaker-aware reframe · validated delivery
            </p>
          </div>
          <nav className="flex items-center gap-1">
            <Tab to="/">Library</Tab>
            <Tab to="/spec">Spec sheet</Tab>
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
  );
}
