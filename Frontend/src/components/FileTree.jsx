import { useState } from "react";

function Node({ node, depth }) {
  const [open, setOpen] = useState(depth < 1);
  const pad = { paddingLeft: depth * 12 + 8 };
  if (node.type === "file") {
    return <div style={pad} className="py-0.5 text-sm text-slate-300 truncate" title={node.path}>📄 {node.name}</div>;
  }
  return (
    <div>
      <button onClick={() => setOpen(!open)} style={pad} className="w-full text-left py-0.5 text-sm text-slate-200 hover:text-cyan-300">
        {open ? "▾" : "▸"} 📁 {node.name}
      </button>
      {open && node.children.map((c) => <Node key={c.path} node={c} depth={depth + 1} />)}
    </div>
  );
}

export default function FileTree({ tree }) {
  return (
    <div className="font-mono">
      {tree.children.map((c) => <Node key={c.path} node={c} depth={0} />)}
    </div>
  );
}
