import { useEffect, useRef, useState } from "react";
import { analyzeScreenshot } from "../api.js";

const BADGE = {
  high: "bg-emerald-500/15 text-emerald-300",
  medium: "bg-amber-500/15 text-amber-300",
  low: "bg-slate-500/20 text-slate-300",
};

function Match({ m, index }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-cyan-400/15 text-xs font-bold text-cyan-300">{index + 1}</span>
        <span className="break-all font-mono text-sm text-cyan-300">
          {m.path}{m.start_line ? `:${m.start_line}-${m.end_line}` : ""}
        </span>
        {m.role && <span className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-300">{m.role}</span>}
        <span className={`rounded px-1.5 py-0.5 text-xs ${BADGE[m.confidence]}`}>{m.confidence} confidence</span>
      </div>
      <p className="mt-2 text-sm text-slate-300">{m.reason}</p>
      {m.evidence && <p className="mt-1 text-sm text-slate-400"><span className="text-slate-500">Evidence: </span>{m.evidence}</p>}
      {m.snippet && (
        <>
          <button onClick={() => setOpen(!open)} className="mt-2 text-xs text-slate-400 hover:text-cyan-300">{open ? "Hide code" : "Show code"}</button>
          {open && (
            <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-3 text-xs text-slate-300">
              {m.snippet.split("\n").map((l, i) => `${String(m.start_line + i).padStart(4)}  ${l}`).join("\n")}
            </pre>
          )}
        </>
      )}
    </div>
  );
}

export default function Screenshot({ id }) {
  const input = useRef();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState("");
  const [question, setQuestion] = useState("");
  const [state, setState] = useState(null);
  const [drag, setDrag] = useState(false);

  useEffect(() => {
    if (!file) return setPreview("");
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function pick(f) {
    if (!f) return;
    if (!/^image\/(png|jpeg|webp)$/.test(f.type)) return setState({ error: "Please choose a PNG, JPEG, or WebP image." });
    if (f.size > 5 * 1024 * 1024) return setState({ error: "Image must be under 5 MB." });
    setState(null);
    setFile(f);
  }

  async function run() {
    setState({ loading: true });
    try {
      setState({ data: await analyzeScreenshot(id, file, question) });
    } catch (e) {
      setState({ error: e.message });
    }
  }

  const d = state?.data;
  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold text-slate-400">Which files power this screen?</h2>
      <div className="grid gap-4 md:grid-cols-2">
        <div
          onClick={() => input.current.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
          className={`flex min-h-48 cursor-pointer items-center justify-center rounded-xl border-2 border-dashed p-4 text-center transition
            ${drag ? "border-cyan-400 bg-cyan-400/5" : "border-slate-700 bg-slate-900/50 hover:border-slate-500"}`}
        >
          <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => pick(e.target.files[0])} />
          {preview ? (
            <img src={preview} alt="Screenshot preview" className="max-h-64 rounded" />
          ) : (
            <div><p className="font-medium">Drop a screenshot here</p><p className="mt-1 text-sm text-slate-500">PNG, JPEG or WebP, up to 5 MB</p></div>
          )}
        </div>
        <div className="flex flex-col gap-3">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={500}
            placeholder="Optional: e.g. Where is this sign-in button defined?"
            className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm outline-none focus:border-cyan-400"
          />
          <button onClick={run} disabled={!file || state?.loading}
            className="rounded-lg bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-40">
            {state?.loading ? "Analyzing…" : "Find matching files"}
          </button>
          <p className="text-xs text-slate-500">Gemma reads the screenshot, then compares it with likely UI files in this repository.</p>
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {state?.loading && (
          <div className="flex items-center gap-3 text-sm text-slate-400">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-400" /> Reading the screenshot and matching code…
          </div>
        )}
        {state?.error && <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">{state.error}</div>}
        {d && (
          <>
            <div className="rounded-lg border border-cyan-400/30 bg-cyan-400/5 p-4">
              <div className="flex items-center gap-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-cyan-400">What Gemma sees</p>
                <span className={`rounded px-1.5 py-0.5 text-xs ${BADGE[d.overall_confidence]}`}>overall: {d.overall_confidence}</span>
              </div>
              <p className="mt-1 text-slate-100">{d.screen_summary}</p>
            </div>
            {d.matches.length === 0 && <p className="text-sm text-amber-300/90">No confident match found in this repository.</p>}
            {d.matches.map((m, i) => <Match key={m.path} m={m} index={i} />)}
            {d.uncertainty && <p className="text-sm text-slate-400"><span className="text-slate-500">Uncertainty: </span>{d.uncertainty}</p>}
            {d.removed_unverified_paths.length > 0 && (
              <p className="text-xs text-amber-400/80">{d.removed_unverified_paths.length} path(s) suggested by the model were removed because they don't exist in this repository.</p>
            )}
            <p className="text-xs text-slate-600">{d.disclaimer}</p>
          </>
        )}
      </div>
    </section>
  );
}
