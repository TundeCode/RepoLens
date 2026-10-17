import { useState } from "react";
import Upload from "./components/Upload.jsx";
import Dashboard from "./components/Dashboard.jsx";
import { getRepo } from "./api.js";

export default function App() {
  const [repo, setRepo] = useState(null);

  async function onUploaded(meta) {
    const full = await getRepo(meta.repository_id); // adds the file tree
    setRepo(full);
  }

  return repo ? (
    <Dashboard repo={repo} onReset={() => setRepo(null)} />
  ) : (
    <Upload onUploaded={onUploaded} />
  );
}
