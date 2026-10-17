import { useEffect, useState } from "react";
import { getOverview, askQuestion } from "../api.js";
import FileTree from "./FileTree.jsx";
import Results from "./Results.jsx";

const EXAMPLES = [
  "How does the login system work?",
  "Where should I add a new API endpoint?",
  "Which files handle database operations?",
  "I want to add dark mode. Where should I start?",
];

const Spinner = ({ label }) => (
  <div className="flex items-center gap-3 text-sm text-slate-400">
    <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-400" /> {label}
  </div>
);
const ErrorBox = ({ msg, onRetry }) => (
  <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
    {msg} {onRetry && <button onClick={onRetry} className="ml-2 underline">Retry</button>}
  </div>
);
const Section = ({ title, children }) =>
  children ? (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</h4>
      <div className="mt-1 text-sm text-slate-300">{children}</div>
    </div>
  ) : null;

function Overview({ id }) {
  const [state, setState] = useState({ loading: true });

  function load() {
    setState({ loading: true });
    getOverview(id).then((data) => setState({ data })).catch((e) => setState({ error: e.message }));
  }
  useEffect(load, [id]);

  if (state.loading) return <Spinner label="Gemma is reading the repository…" />;
  if (state.error) return <ErrorBox msg={state.error} onRetry={load} />;
  const o = state.data;
  return (
    <div className="space-y-4">
      <p className="text-slate-100">{o.purpose}</p>
      <div className="flex flex-wrap gap-2">
        {[...o.languages, ...o.frameworks].map((t) => (
          <span key={t} className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-300">{t}</span>
        ))}
      </div>
      <Section title="Architecture">{o.architecture}</Section>
      <Section title="How the pieces interact">{o.component_interactions}</Section>
      {o.entry_points.length > 0 && (
        <Section title="Entry points">
          {o.entry_points.map((p) => <div key={p} className="font-mono text-cyan-300/90">{p}</div>)}
        </Section>
      )}
      {o.key_files.length > 0 && (
        <Section title="Important files">
          {o.key_files.map((k) => (
            <div key={k.path}><span className="font-mono text-cyan-300/90">{k.path}</span> — {k.why}</div>
          ))}
        </Section>
      )}
      {o.start_here.length > 0 && (
        <Section title="Start here"><ul className="list-disc pl-5">{o.start_here.map((s, i) => <li key={i}>{s}</li>)}</ul></Section>
      )}
      {o.unknowns.length > 0 && (
        <Section title="Could not determine"><ul className="list-disc pl-5 text-slate-400">{o.unknowns.map((s, i) => <li key={i}>{s}</li>)}</ul></Section>
      )}
    </div>
  );
}

export default function Dashboard({ repo, onReset }) {
  const [question, setQuestion] = useState("");
  const [ask, setAsk] = useState(null);

  async function submit(q = question) {
    if (q.trim().length < 3) return;
    setQuestion(q);
    setAsk({ loading: true });
    try {
      setAsk({ data: await askQuestion(repo.repository_id, q) });
    } catch (e) {
      setAsk({ error: e.message });
    }
  }

  const langs = Object.entries(repo.languages).slice(0, 5);
  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-72 shrink-0 flex-col border-r border-slate-800 bg-slate-900/60 md:flex">
        <div className="border-b border-slate-800 p-4">
          <button onClick={onReset} className="text-lg font-bold">Repo<span className="text-cyan-400">Lens</span></button>
          <p className="mt-3 truncate font-semibold" title={repo.name}>{repo.name}</p>
          <p className="text-xs text-slate-500">{repo.file_count} files · {repo.skipped_files} skipped</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {langs.map(([l, n]) => <span key={l} className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-300">{l} {n}</span>)}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2"><FileTree tree={repo.tree} /></div>
      </aside>

      <main className="min-w-0 flex-1 space-y-8 p-6 md:p-10">
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-400">Project overview</h2>
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <Overview id={repo.repository_id} />
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-400">Where do I start?</h2>
          <div className="flex gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              maxLength={1000}
              placeholder="e.g. Where would I add Google authentication?"
              className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm outline-none focus:border-cyan-400"
            />
            <button onClick={() => submit()} disabled={ask?.loading}
              className="rounded-lg bg-cyan-500 px-5 text-sm font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50">
              Ask
            </button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((e) => (
              <button key={e} onClick={() => submit(e)} className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-cyan-400 hover:text-cyan-300">{e}</button>
            ))}
          </div>
          <div className="mt-6">
            {ask?.loading && <Spinner label="Finding the right files…" />}
            {ask?.error && <ErrorBox msg={ask.error} onRetry={() => submit()} />}
            {ask?.data && <Results data={ask.data} />}
          </div>
        </section>
      </main>
    </div>
  );
}
