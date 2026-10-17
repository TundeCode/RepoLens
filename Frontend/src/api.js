// All backend calls live here. Vite proxies /api to the FastAPI server.
async function handle(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : `Request failed (${res.status})`);
  }
  return data;
}

export function uploadRepo(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/repositories/upload");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onerror = () => reject(new Error("Cannot reach the backend. Is it running on port 8000?"));
    xhr.onload = () => {
      let data = {};
      try { data = JSON.parse(xhr.responseText); } catch { /* non-JSON error */ }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data);
      reject(new Error(typeof data.detail === "string" ? data.detail : `Upload failed (${xhr.status})`));
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

export const getRepo = (id) => fetch(`/api/repositories/${id}`).then(handle);
export const getOverview = (id) => fetch(`/api/repositories/${id}/overview`).then(handle);
export const askQuestion = (id, question) =>
  fetch(`/api/repositories/${id}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  }).then(handle);

export function analyzeScreenshot(id, file, question) {
  const form = new FormData();
  form.append("file", file);
  form.append("question", question || "");
  return fetch(`/api/repositories/${id}/screenshot`, { method: "POST", body: form }).then(handle);
}