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
      className={({ isActive }) => clsx(isActive ? "tab-active" : "tab-inactive")}
    >
      {children}
    </NavLink>
  );
}

/**
 * Scrolling ticker under the header. Purely decorative, but it keeps the page
 * alive while a render grinds away in the background — and it restates what
 * the thing actually does, which is useful the first time you land here.
 */
function Ticker() {
  const items = [
    "SUBJECT-AWARE CROP",
    "★",
    "SPEAKER-TRACKED REFRAME",
    "★",
    "MACHINE-READABLE SPEC",
    "★",
    "NOTHING SHIPS UNVALIDATED",
    "★",
    "16:9 · 1:1 · 9:16 · 4:5",
    "★",
  ];
  return (
    <div className="overflow-hidden border-b-3 border-ink-600 bg-pop-yellow py-1.5">
      <div className="flex w-max animate-marquee" aria-hidden="true">
        {[0, 1].map((copy) => (
          <div key={copy} className="flex shrink-0">
            {items.map((item, i) => (
              <span
                key={`${copy}-${i}`}
                className="px-4 font-mono text-[11px] font-bold uppercase tracking-[0.18em] text-black"
              >
                {item}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b-5 border-ink-600 bg-ink-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-3">
          <NavLink to="/" className="group flex items-center gap-3">
            {/* Logo tile: tilts upright when you hover it. */}
            <div
              className="flex h-11 w-11 -rotate-3 items-center justify-center rounded-brutal
                         border-3 border-ink-600 bg-accent text-xl shadow-brutal
                         transition-transform duration-150 group-hover:rotate-3 group-hover:scale-105"
            >
              🎬
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-display text-base leading-none text-slate-100">
                  CREATIVE REFORMATTING
                </h1>
                <span className="sticker bg-pop-cyan text-black">hoichoi</span>
              </div>
              <p className="mt-1 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                one master in · every ratio out
              </p>
            </div>
          </NavLink>

          <nav className="flex items-center gap-2">
            <Tab to="/">Library</Tab>
            <Tab to="/spec">Spec</Tab>
          </nav>
        </div>
        <Ticker />
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-5 py-8">
        <Routes>
          <Route path="/" element={<LibraryPage />} />
          <Route path="/assets/:assetId" element={<AssetPage />} />
          <Route path="/spec" element={<SpecPage />} />
        </Routes>
      </main>

      <footer className="mt-10 border-t-5 border-ink-600 bg-black">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-6">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 rotate-3 items-center justify-center rounded-brutal border-3 border-white bg-pop-yellow text-lg">
              🎬
            </span>
            <div>
              <p className="font-display text-sm text-white">CREATIVE REFORMATTING ENGINE</p>
              <p className="text-[11px] font-bold uppercase tracking-wider text-pop-cyan">
                media pipeline · computer vision
              </p>
            </div>
          </div>

          <p className="text-sm font-bold text-white">
            Built by{" "}
            <a
              href="https://openworld.aritro.cloud"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block rounded-brutal border-3 border-white bg-accent px-2 py-0.5 text-white
                         transition-transform duration-100 hover:-translate-y-0.5 hover:rotate-2"
            >
              Aritro Saha ↗
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
