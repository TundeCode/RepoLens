import { useState } from "react";

function FileCard({ f, index }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan-400/15 text-xs font-bold text-cyan-300">{index + 1}</span>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-sm text-cyan-300 break-all">
            {f.path}{f.start_line ? `:${f.start_line}-${f.end_line}` : ""}
          </p>
          <p className="mt-1 text-sm text-slate-300">{f.reason}</p>
          {f.snippet && (
            <>
              <button onClick={() => setOpen(!open)} className="mt-2 text-xs text-slate-400 hover:text-cyan-300">
                {open ? "Hide code" : "Show code"}
              </button>
              {open && (
                <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-3 text-xs text-slate-300">
                  {f.snippet.split("\n").map((l, i) => `${String(f.start_line + i).padStart(4)}  ${l}`).join("\n")}
                </pre>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const List = ({ title, items, mono }) =>
  items?.length ? (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</h4>
      <ol className="mt-2 space-y-1 text-sm text-slate-300">
        {items.map((x, i) => <li key={i} className={mono ? "font-mono text-cyan-300/90 break-all" : ""}>{x}</li>)}
      </ol>
    </div>
  ) : null;

export default function Results({ data }) {
  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-cyan-400/30 bg-cyan-400/5 p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-cyan-400">Answer</p>
        <p className="mt-1 text-slate-100">{data.summary}</p>
      </div>
      {data.files.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-slate-400">Relevant files, in suggested order</h3>
          {data.files.map((f, i) => <FileCard key={f.path} f={f} index={i} />)}
        </div>
      )}
      <div className="grid gap-5 md:grid-cols-2">
        <List title="Exploration order" items={data.exploration_order} mono />
        <List title="Also inspect" items={data.related_to_inspect} mono />
      </div>
      <List title="Caveats" items={data.caveats} />
      {data.removed_unverified_paths?.length > 0 && (
        <p className="text-xs text-amber-400/80">
          {data.removed_unverified_paths.length} path(s) suggested by the model were removed because they don't exist in this repository.
        </p>
      )}
      <p className="text-xs text-slate-600">{data.disclaimer}</p>
    </div>
  );
}
