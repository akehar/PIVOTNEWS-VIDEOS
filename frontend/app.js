// Thin dashboard for the pivotnews.ai video pipeline.
const $ = (id) => document.getElementById(id);

const DEFAULT_API =
  localStorage.getItem("apiBase") ||
  (location.hostname === "localhost" ? "http://localhost:8000" : location.origin);

let config = null;
let currentJob = null;
let pollTimer = null;

function api() {
  return $("apiBase").value.replace(/\/$/, "");
}
async function req(method, path, body) {
  const opt = { method, headers: {} };
  if (body !== undefined) {
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  const r = await fetch(api() + path, opt);
  if (!r.ok) throw new Error(`${method} ${path} -> ${r.status} ${await r.text()}`);
  return r.status === 204 ? null : r.json();
}

// ---- config ----
async function loadConfig() {
  config = await req("GET", "/config");
  $("configJson").value = JSON.stringify(config, null, 2);
  const desk = $("desk");
  desk.innerHTML = "";
  (config.writers || []).forEach((w) => {
    const o = document.createElement("option");
    o.value = w.desk;
    o.textContent = `${w.desk} — ${w.writer}`;
    o.dataset.writer = w.writer;
    desk.appendChild(o);
  });
  updateWriterLabel();
}
function updateWriterLabel() {
  const opt = $("desk").selectedOptions[0];
  $("writerLabel").textContent = opt ? `writer ${opt.dataset.writer}` : "writer —";
}
async function saveConfig() {
  try {
    const parsed = JSON.parse($("configJson").value);
    await req("PUT", "/config", parsed);
    $("configMsg").textContent = "saved ✓";
    await loadConfig();
  } catch (e) {
    $("configMsg").textContent = "error: " + e.message;
  }
}

// ---- jobs ----
async function createJob() {
  $("createMsg").textContent = "creating…";
  try {
    const job = await req("POST", "/jobs", {
      desk: $("desk").value,
      topics: $("topics").value,
      autostart: true,
    });
    $("createMsg").textContent = "";
    openJob(job.id);
  } catch (e) {
    $("createMsg").textContent = e.message;
  }
}

function openJob(id) {
  $("job").classList.remove("hidden");
  $("jobId").textContent = id;
  startPolling(id);
}

function startPolling(id) {
  clearInterval(pollTimer);
  const tick = async () => {
    try {
      currentJob = await req("GET", `/jobs/${id}`);
      renderJob(currentJob);
      const done = ["complete", "failed"].includes(currentJob.state);
      const anyRunning = currentJob.stages.some((s) => s.state === "running");
      if (done && !anyRunning) clearInterval(pollTimer);
    } catch (e) {
      $("jobState").textContent = "error";
    }
  };
  tick();
  pollTimer = setInterval(tick, 3000);
}

async function renderJob(job) {
  const st = $("jobState");
  st.textContent = job.state;
  st.className = "pill " + job.state;

  $("stages").innerHTML = job.stages
    .map(
      (s) =>
        `<div class="stage"><span class="dot ${s.state}"></span>${s.name}` +
        (s.error ? ` <span class="muted" title="${escapeAttr(s.error)}">⚠</span>` : "") +
        `</div>`
    )
    .join("");

  // final video
  const artifacts = await req("GET", `/jobs/${job.id}/artifacts`);
  const final = artifacts.find((a) => a.label === "final_video");
  if (final) {
    $("finalWrap").classList.remove("hidden");
    $("finalVideo").src = final.url;
    $("finalDownload").href = final.url;
  } else {
    $("finalWrap").classList.add("hidden");
  }

  renderBeats(job, artifacts);
}

function renderBeats(job, artifacts) {
  const byLabel = Object.fromEntries(artifacts.map((a) => [a.label, a.url]));
  const beats = (job.script && job.script.beats) || [];
  $("beats").innerHTML = "";
  beats.forEach((b) => {
    const meta = (job.beats || []).find((x) => x.beat_id === b.id) || {};
    const img = byLabel[`beat_${b.id}_image`];
    const clip = byLabel[`beat_${b.id}_clip`];
    const el = document.createElement("div");
    el.className = "beat";
    el.innerHTML = `
      <div class="row"><b>Beat ${b.id}</b><span class="spacer"></span>
        <span class="time">${fmt(meta.start_seconds)}–${fmt(meta.end_seconds)}s</span></div>
      <div class="time">${escapeHtml(b.narration)}</div>
      <div class="media">
        ${img ? `<img src="${img}" />` : `<div class="img muted">no image</div>`}
        ${clip ? `<video src="${clip}" muted controls></video>` : `<div class="muted">no clip</div>`}
      </div>
      <label>image prompt<textarea rows="2" data-f="image_prompt">${escapeHtml(b.image_prompt)}</textarea></label>
      <label>motion prompt<textarea rows="2" data-f="motion_prompt">${escapeHtml(b.motion_prompt)}</textarea></label>
      <button data-act="regen">Save prompts &amp; regenerate</button>
      <span class="muted regenMsg"></span>`;
    el.querySelector('[data-act="regen"]').onclick = () => regenBeat(job.id, b.id, el);
    $("beats").appendChild(el);
  });
}

async function regenBeat(jobId, beatId, el) {
  const msg = el.querySelector(".regenMsg");
  msg.textContent = "working…";
  try {
    const patch = {};
    el.querySelectorAll("textarea[data-f]").forEach((t) => (patch[t.dataset.f] = t.value));
    await req("PATCH", `/jobs/${jobId}/beats/${beatId}`, patch);
    await req("POST", `/jobs/${jobId}/beats/${beatId}/regenerate`);
    msg.textContent = "done ✓";
    startPolling(jobId);
  } catch (e) {
    msg.textContent = e.message;
  }
}

// ---- helpers ----
const fmt = (n) => (n == null ? "?" : Number(n).toFixed(1));
const escapeHtml = (s) =>
  (s || "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const escapeAttr = (s) => escapeHtml(s).replace(/"/g, "&quot;");

// ---- wire up ----
$("apiBase").value = DEFAULT_API;
$("apiBase").onchange = () => {
  localStorage.setItem("apiBase", $("apiBase").value);
  loadConfig();
};
$("desk").onchange = updateWriterLabel;
$("createBtn").onclick = createJob;
$("refreshBtn").onclick = () => currentJob && startPolling(currentJob.id);
$("reloadConfig").onclick = loadConfig;
$("saveConfig").onclick = saveConfig;
$("tabConfig").onclick = () => $("configCard").classList.toggle("hidden");

loadConfig().catch((e) => ($("createMsg").textContent = e.message));
