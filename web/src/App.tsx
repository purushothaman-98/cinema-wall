import { Route, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { Overview } from "./pages/Overview";
import { Films } from "./pages/Films";
import { FilmDetail } from "./pages/FilmDetail";
import { Channels } from "./pages/Channels";

export default function App() {
  return (
    <div className="min-h-screen">
      <Nav />
      <main className="mx-auto max-w-6xl px-5 py-8">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/films" element={<Films />} />
          <Route path="/films/:film" element={<FilmDetail />} />
          <Route path="/channels" element={<Channels />} />
        </Routes>
      </main>
      <footer className="mx-auto max-w-6xl px-5 pb-10 pt-4 text-xs text-ink-500">
        Counts describe the collected public sample. They are not unique viewers, representative polling, box-office
        estimates or objective film ratings.
      </footer>
    </div>
  );
}
