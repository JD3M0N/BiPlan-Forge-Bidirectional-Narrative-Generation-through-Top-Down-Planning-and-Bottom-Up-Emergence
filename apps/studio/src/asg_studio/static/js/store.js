// Estado compartido de la página, y lo único que se guarda en el navegador: el borrador de la
// obra y la selección para comparar. Todo acceso al almacenamiento va en try/catch: en una
// ventana privada o con el almacenamiento bloqueado, la página sigue funcionando sin él.

const DRAFT_KEY = "stagecraft.draft.v1";
const PICKS_KEY = "stagecraft.picks.v1";

export const state = {
  health: null,
  catalog: null,
  form: null,
  job: null,
  runs: null,
  picks: readJson(PICKS_KEY, []),
};

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* sin almacenamiento: la página funciona igual */
  }
}

export function loadDraft() {
  return readJson(DRAFT_KEY, null);
}

export function saveDraft(form) {
  writeJson(DRAFT_KEY, form);
}

export function togglePick(reference) {
  const picks = state.picks.includes(reference)
    ? state.picks.filter((item) => item !== reference)
    : [...state.picks, reference].slice(-4);
  state.picks = picks;
  writeJson(PICKS_KEY, picks);
  return picks;
}

export function setPicks(picks) {
  state.picks = picks.slice(0, 4);
  writeJson(PICKS_KEY, state.picks);
}
