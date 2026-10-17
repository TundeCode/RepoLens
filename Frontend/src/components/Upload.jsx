import { useRef, useState } from "react";
import { uploadRepo } from "../api.js";

export default function Upload({ onUploaded }) {
  const input = useRef();
  const [drag, setDrag] = useState(false);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState("");

  async function handle(file) {
    setError("");
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".zip")) return setError("Please choose a .zip file.");
    try {
      setProgress(0);
      const meta = await uploadRepo(file, setProgress);
      setProgress(100);
      await onUploaded(meta);
    } catch (e) {
      setError(e.message);
      setProgress(null);
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6">
      <h1 className="text-5xl font-bold tracking-tight">
        Repo<span className="text-cyan-400">Lens</span>
      </h1>
      <p className="mt-3 text-slate-400 text-lg">Understand any codebase in minutes, not hours.</p>

      <div
        onClick={() => progress === null && input.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files[0]); }}
        className={`mt-10 w-full max-w-xl cursor-pointer rounded-xl border-2 border-dashed p-12 text-center transition
          ${drag ? "border-cyan-400 bg-cyan-400/5" : "border-slate-700 hover:border-slate-500 bg-slate-900/50"}`}
      >
        <input ref={input} type="file" accept=".zip" className="hidden" onChange={(e) => handle(e.target.files[0])} />
        {progress === null ? (
          <>
            <p className="text-lg font-medium">Drop a repository ZIP here</p>
            <p className="mt-1 text-sm text-slate-500">or click to browse. Code is read, never executed.</p>
          </>
        ) : (
          <div>
            <p className="font-medium">{progress < 100 ? `Uploading… ${progress}%` : "Indexing repository…"}</p>
            <div className="mt-4 h-2 rounded bg-slate-800 overflow-hidden">
              <div className="h-full bg-cyan-400 transition-all" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}
      </div>
      {error && (
        <p className="mt-4 max-w-xl rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm text-red-300">{error}</p>
      )}
    </main>
  );
}
