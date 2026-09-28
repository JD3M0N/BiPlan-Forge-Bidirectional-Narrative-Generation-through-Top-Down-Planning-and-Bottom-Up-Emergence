// Todas las llamadas al servidor. Cada petición lleva la cabecera X-StageCraft: el servidor
// rechaza cualquier escritura sin ella, y otra web no puede añadirla.

const HEADERS = { "Content-Type": "application/json", "X-StageCraft": "1" };
const enc = encodeURIComponent;

async function request(method, url, body) {
  const response = await fetch(url, {
    method,
    headers: HEADERS,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!response.ok) {
    const error = new Error((data && data.detail) || `Error ${response.status}`);
    error.status = response.status;
    error.problems = (data && data.problems) || [];
    throw error;
  }
  return data;
}

export const api = {
  health: () => request("GET", "/api/health"),
  catalog: () => request("GET", "/api/catalog"),
  preview: (job) => request("POST", "/api/preview", job),
  submit: (job) => request("POST", "/api/jobs", job),
  jobs: () => request("GET", "/api/jobs"),
  job: (id, since) => request("GET", `/api/jobs/${enc(id)}?since=${since || 0}`),
  cancel: (id) => request("POST", `/api/jobs/${enc(id)}/cancel`),
  runs: () => request("GET", "/api/runs"),
  run: (collection, runId) => request("GET", `/api/runs/${enc(collection)}/${enc(runId)}`),
  performance: (collection, runId, voice, narrator) =>
    request(
      "GET",
      `/api/runs/${enc(collection)}/${enc(runId)}/performance?voice=${enc(voice || "")}` +
        `&narrator=${enc(narrator || "")}`,
    ),
  replay: (collection, runId) =>
    request("GET", `/api/runs/${enc(collection)}/${enc(runId)}/replay`),
  compare: (references) => request("GET", `/api/compare?runs=${enc(references.join(","))}`),
  audioUrl: (collection, runId) => `/api/runs/${enc(collection)}/${enc(runId)}/audio`,
  sampleUrl: (voice) => `/api/voices/${enc(voice)}/sample`,
};
