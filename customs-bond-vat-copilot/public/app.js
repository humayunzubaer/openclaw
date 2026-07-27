// Frontend SPA — vanilla JS, no build step. Talks to the local API.

const app = document.getElementById("app");
const api = {
  async get(url) { return (await fetch(url)).json(); },
  async send(method, url, body) {
    const r = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    return r.json();
  },
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const bdt = (n) => Number(n || 0).toLocaleString("en-BD");

let MODULES = [];

// ---------- OCR badge ----------
async function refreshOcrBadge() {
  const badge = document.getElementById("ocr-badge");
  const { available } = await api.get("/api/ocr-status");
  badge.textContent = available ? "OCR: চালু" : "OCR: বন্ধ (npm i tesseract.js)";
  badge.className = "badge " + (available ? "badge-ok" : "badge-off");
}

// ---------- Home / dashboard ----------
async function viewHome() {
  const audits = await api.get("/api/audits");
  const totalRevenue = [];
  const cards = audits.map((a) => {
    const mod = MODULES.find((m) => m.id === a.moduleId);
    return `<div class="card audit-card" data-id="${a.id}">
      <div class="inst">${esc(a.institution || "নামহীন প্রতিষ্ঠান")}</div>
      <div class="meta">${esc(mod?.title || a.moduleId)}</div>
      <div class="meta">Period: ${esc(a.period || "—")} · Auditor: ${esc(a.auditor || "—")}</div>
      <div class="row" style="margin-top:10px"><span class="pill">${esc(a.status)}</span></div>
    </div>`;
  }).join("");

  app.innerHTML = `
    <div class="stat-row">
      <div class="stat"><div class="n">${audits.length}</div><div class="l">মোট অডিট</div></div>
      <div class="stat"><div class="n">${audits.filter(a=>a.status==="in-progress").length}</div><div class="l">চলমান</div></div>
      <div class="stat"><div class="n">${MODULES.filter(m=>m.status==="active").length}</div><div class="l">সক্রিয় মডিউল</div></div>
    </div>
    <div class="section-head"><h2>অডিট তালিকা</h2><button class="btn btn-primary" id="new-audit">+ নতুন অডিট</button></div>
    <div class="grid grid-audits">${cards || `<div class="empty">এখনো কোনো অডিট নেই। "নতুন অডিট" দিয়ে শুরু করুন।</div>`}</div>`;

  document.getElementById("new-audit").onclick = openNewAuditDialog;
  document.querySelectorAll(".audit-card").forEach((el) => (el.onclick = () => viewAudit(el.dataset.id)));
}

function openNewAuditDialog() {
  const dlg = document.getElementById("new-audit-dialog");
  const sel = document.getElementById("module-select");
  sel.innerHTML = MODULES.map((m) =>
    `<option value="${m.id}" ${m.status !== "active" ? "disabled" : ""}>${esc(m.title)}${m.status !== "active" ? " (শীঘ্রই)" : ""}</option>`
  ).join("");
  dlg.showModal();
  document.getElementById("cancel-new").onclick = () => dlg.close();
  document.getElementById("new-audit-form").onsubmit = async (e) => {
    const fd = new FormData(e.target);
    const created = await api.send("POST", "/api/audits", Object.fromEntries(fd));
    dlg.close();
    if (created?.id) viewAudit(created.id);
  };
}

// ---------- Audit workspace ----------
async function viewAudit(id, tab = "dashboard") {
  const { audit, module } = await api.get(`/api/audits/${id}`);
  if (!audit) return viewHome();

  app.innerHTML = `
    <div class="section-head">
      <div><h2>${esc(audit.institution || "নামহীন")}</h2><div class="muted">${esc(module.title)}</div></div>
    </div>
    <div class="tabs" id="tabs">
      ${["dashboard","documents","findings","working-paper","reports","settings"].map((t)=>
        `<div class="tab ${t===tab?"active":""}" data-tab="${t}">${tabLabel(t)}</div>`).join("")}
    </div>
    <div id="tab-body"><div class="loading">লোড হচ্ছে…</div></div>`;

  document.querySelectorAll("#tabs .tab").forEach((el)=> el.onclick = ()=> viewAudit(id, el.dataset.tab));

  const body = document.getElementById("tab-body");
  if (tab === "dashboard") return renderDashboard(body, id, module);
  if (tab === "documents") return renderDocuments(body, id, module);
  if (tab === "findings") return renderFindings(body, id, module);
  if (tab === "working-paper") return renderWorkingPaper(body, id, module);
  if (tab === "reports") return renderReports(body, id);
  if (tab === "settings") return renderSettings(body);
}

const tabLabel = (t) => ({ dashboard:"📊 ড্যাশবোর্ড", documents:"📁 নথি", findings:"🔍 Findings", "working-paper":"📝 Working Paper", reports:"📄 রিপোর্ট", settings:"⚙️ সেটিংস" }[t]);

async function renderDashboard(body, id, module) {
  const [docs, findings] = await Promise.all([api.get(`/api/audits/${id}/documents`), api.get(`/api/audits/${id}/findings`)]);
  const required = module.documentTypes.filter((d)=>d.required);
  const present = new Set(docs.map((d)=>d.category));
  const collected = required.filter((d)=>present.has(d.id)).length;
  const totalRev = findings.reduce((s,f)=>s+Number(f.revenueImplication||0),0);
  const high = findings.filter((f)=>f.severity==="high").length;

  body.innerHTML = `
    <div class="stat-row">
      <div class="stat"><div class="n">${collected}/${required.length}</div><div class="l">আবশ্যক নথি সংগৃহীত</div></div>
      <div class="stat"><div class="n">${findings.length}</div><div class="l">Findings</div></div>
      <div class="stat"><div class="n" style="color:var(--high)">${high}</div><div class="l">গুরুতর (High)</div></div>
      <div class="stat"><div class="n">৳${bdt(totalRev)}</div><div class="l">সম্ভাব্য রাজস্ব প্রভাব</div></div>
    </div>
    <div class="card">
      <h3>আবশ্যক নথি চেকলিস্ট</h3>
      ${required.map((d)=>`<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--line);padding:6px 0">
        <span>${present.has(d.id)?"✅":"⬜"} ${esc(d.label)}</span></div>`).join("")}
    </div>`;
}

async function renderDocuments(body, id, module) {
  const docs = await api.get(`/api/audits/${id}/documents`);
  const opts = module.documentTypes.map((d)=>`<option value="${d.id}">${esc(d.label)}</option>`).join("");
  body.innerHTML = `
    <div class="card" style="margin-bottom:16px">
      <h3>নথি আপলোড</h3>
      <div class="row">
        <select id="doc-cat" style="max-width:340px">${opts}</select>
        <input type="file" id="doc-file" multiple style="max-width:320px" />
        <button class="btn btn-primary" id="upload-btn">আপলোড</button>
      </div>
      <div class="hint">PDF/ছবি/যেকোনো ফাইল। আপলোডের পর "OCR" চেপে টেক্সট বের করুন (OCR চালু থাকলে)।</div>
    </div>
    <div id="doc-list">${docs.length?"":`<div class="empty">কোনো নথি নেই।</div>`}
      ${docs.map(docRow).join("")}</div>`;

  document.getElementById("upload-btn").onclick = async () => {
    const cat = document.getElementById("doc-cat").value;
    const files = document.getElementById("doc-file").files;
    if (!files.length) return;
    for (const f of files) {
      const base64 = await fileToBase64(f);
      await api.send("POST", `/api/audits/${id}/documents`, { filename: f.name, category: cat, base64 });
    }
    renderDocuments(body, id, module);
  };
  bindDocActions(body, id, module);
}

function docRow(d) {
  const ocr = d.ocrStatus === "done" ? `<span class="pill">OCR ✓ (${(d.ocrText||"").length} chars)</span>` :
    d.ocrStatus === "failed" ? `<span class="pill">OCR ✗</span>` : "";
  return `<div class="doc-item" data-doc="${d.id}">
    <div class="row" style="justify-content:space-between">
      <div><strong>${esc(d.filename)}</strong> <span class="pill">${esc(d.category)}</span> ${ocr}</div>
      <div class="row">
        <a class="btn btn-ghost btn-sm" href="/api/audits/${d._auditId||""}" style="display:none"></a>
        <button class="btn btn-ghost btn-sm act-ocr">OCR</button>
        <button class="btn btn-ghost btn-sm act-view">দেখুন</button>
      </div>
    </div>
    ${d.ocrText ? `<details style="margin-top:8px"><summary class="muted">OCR টেক্সট</summary><pre style="white-space:pre-wrap">${esc(d.ocrText.slice(0,4000))}</pre></details>`:""}
  </div>`;
}

function bindDocActions(body, id, module) {
  body.querySelectorAll(".doc-item").forEach((el) => {
    const docId = el.dataset.doc;
    el.querySelector(".act-view").onclick = () => window.open(`/api/audits/${id}/documents/${docId}/file`, "_blank");
    el.querySelector(".act-ocr").onclick = async (e) => {
      e.target.textContent = "OCR চলছে…"; e.target.disabled = true;
      const r = await api.send("POST", `/api/audits/${id}/documents/${docId}/ocr`);
      if (r.error === "OCR_NOT_INSTALLED") alert("OCR চালু নেই। টার্মিনালে চালান:\n\ncd customs-bond-vat-copilot\nnpm install tesseract.js\n\nতারপর সার্ভার রিস্টার্ট করুন।");
      renderDocuments(body, id, module);
    };
  });
}

async function renderFindings(body, id, module) {
  const findings = await api.get(`/api/audits/${id}/findings`);
  body.innerHTML = `
    <div class="row" style="justify-content:space-between;margin-bottom:14px">
      <h3 style="margin:0">Findings (${findings.length})</h3>
      <div class="row">
        <button class="btn btn-ghost" id="ai-draft">🤖 খসড়া তৈরি</button>
        <button class="btn btn-primary" id="add-finding">+ Finding যোগ</button>
      </div>
    </div>
    <div id="find-list">${findings.length?findings.map((f)=>findingRow(f, module)).join(""):`<div class="empty">কোনো finding নেই। checklist থেকে খসড়া তৈরি করুন বা ম্যানুয়ালি যোগ করুন।</div>`}</div>`;

  document.getElementById("add-finding").onclick = () => addOrEditFinding(id, module, null, () => renderFindings(body, id, module));
  document.getElementById("ai-draft").onclick = async () => {
    if (!confirm("সেটিংসে নির্বাচিত provider দিয়ে খসড়া findings তৈরি হবে। এগুলো সম্পাদনাযোগ্য। এগিয়ে যাবেন?")) return;
    const r = await api.send("POST", `/api/audits/${id}/analyze`, {});
    if (r.error) return alert("বিশ্লেষণ ব্যর্থ: " + (r.message || r.error));
    for (const d of r.drafts) await api.send("POST", `/api/audits/${id}/findings`, d);
    renderFindings(body, id, module);
  };
  body.querySelectorAll(".finding-item").forEach((el) => {
    const fid = el.dataset.find;
    el.querySelector(".act-edit").onclick = () => addOrEditFinding(id, module, findings.find((f)=>f.id===fid), ()=>renderFindings(body,id,module));
    el.querySelector(".act-del").onclick = async () => { if(confirm("মুছে ফেলবেন?")){ await api.send("DELETE", `/api/audits/${id}/findings/${fid}`); renderFindings(body,id,module);} };
  });
}

function findingRow(f, module) {
  return `<div class="finding-item ${esc(f.severity)}" data-find="${f.id}">
    <div class="row" style="justify-content:space-between">
      <strong>${esc(f.title || f.area)}</strong>
      <div class="row"><span class="pill">${esc(f.area)}</span>
        <button class="btn btn-ghost btn-sm act-edit">সম্পাদনা</button>
        <button class="btn btn-ghost btn-sm act-del">মুছুন</button></div>
    </div>
    <div style="margin-top:6px">${esc(f.observation)}</div>
    <div class="row muted" style="margin-top:6px;font-size:13px">
      ${f.legalRef?`আইন: ${esc(f.legalRef)} · `:""}রাজস্ব: ৳${bdt(f.revenueImplication)} · severity: ${esc(f.severity)}</div>
  </div>`;
}

function addOrEditFinding(id, module, existing, done) {
  const areas = [...new Set(module.checklist.map((c)=>c.area))];
  const legalOpts = [...new Set(module.checklist.map((c)=>c.legalRef).filter(Boolean))];
  const dlg = document.createElement("dialog");
  dlg.innerHTML = `<form method="dialog">
    <h3>${existing?"Finding সম্পাদনা":"নতুন Finding"}</h3>
    <label>শিরোনাম<input name="title" value="${esc(existing?.title||"")}" /></label>
    <label>Area<select name="area">${areas.map((a)=>`<option ${existing?.area===a?"selected":""}>${esc(a)}</option>`).join("")}</select></label>
    <label>পর্যবেক্ষণ<textarea name="observation">${esc(existing?.observation||"")}</textarea></label>
    <div class="row">
      <label style="flex:1">আইন রেফারেন্স<select name="legalRef"><option value="">—</option>${legalOpts.map((l)=>`<option ${existing?.legalRef===l?"selected":""}>${esc(l)}</option>`).join("")}</select></label>
      <label style="flex:1">Severity<select name="severity">${["low","medium","high"].map((s)=>`<option ${(existing?.severity||"medium")===s?"selected":""}>${s}</option>`).join("")}</select></label>
    </div>
    <label>রাজস্ব প্রভাব (BDT)<input name="revenueImplication" type="number" value="${existing?.revenueImplication||0}" /></label>
    <div class="row-end"><button type="button" class="btn btn-ghost" id="fc">বাতিল</button><button class="btn btn-primary">সংরক্ষণ</button></div>
  </form>`;
  document.body.appendChild(dlg); dlg.showModal();
  dlg.querySelector("#fc").onclick = () => { dlg.close(); dlg.remove(); };
  dlg.querySelector("form").onsubmit = async () => {
    const data = Object.fromEntries(new FormData(dlg.querySelector("form")));
    data.revenueImplication = Number(data.revenueImplication) || 0;
    if (existing) await api.send("PATCH", `/api/audits/${id}/findings/${existing.id}`, data);
    else await api.send("POST", `/api/audits/${id}/findings`, data);
    dlg.close(); dlg.remove(); done();
  };
}

async function renderWorkingPaper(body, id, module) {
  const wp = await api.get(`/api/audits/${id}/working-paper`);
  wp.sections = wp.sections || {};
  body.innerHTML = `
    <div class="card">
      <div class="row" style="justify-content:space-between"><h3 style="margin:0">Working Paper</h3>
        <button class="btn btn-primary" id="wp-save">সংরক্ষণ</button></div>
      ${module.workingPaperSections.map((s,i)=>`
        <label>${i+1}. ${esc(s)}<textarea data-section="${esc(s)}">${esc(wp.sections[s]||"")}</textarea></label>`).join("")}
    </div>`;
  document.getElementById("wp-save").onclick = async () => {
    const sections = {};
    body.querySelectorAll("textarea[data-section]").forEach((t)=> sections[t.dataset.section]=t.value);
    await api.send("PUT", `/api/audits/${id}/working-paper`, { sections });
    document.getElementById("wp-save").textContent = "✓ সংরক্ষিত";
    setTimeout(()=>document.getElementById("wp-save").textContent="সংরক্ষণ", 1500);
  };
}

async function renderReports(body, id) {
  body.innerHTML = `
    <div class="card" style="margin-bottom:14px">
      <div class="row" style="justify-content:space-between">
        <div class="row">
          <span class="muted">প্রিভিউ:</span>
          <button class="btn btn-ghost btn-sm" data-kind="working-paper">Working Paper</button>
          <button class="btn btn-ghost btn-sm" data-kind="note-sheet">Note Sheet</button>
          <button class="btn btn-ghost btn-sm" data-kind="final">চূড়ান্ত রিপোর্ট</button>
        </div>
        <div class="row">
          <span class="muted">Export:</span>
          <button class="btn btn-primary btn-sm" data-export="word">📄 Word</button>
          <button class="btn btn-primary btn-sm" data-export="excel">📊 Excel</button>
          <button class="btn btn-primary btn-sm" data-export="pdf">📕 PDF</button>
        </div>
      </div>
    </div>
    <div class="report-out" id="report-out"><div class="muted">প্রিভিউ দেখতে উপরের বাটন চাপুন, অথবা সরাসরি Word/Excel/PDF export করুন।</div></div>`;
  body.querySelectorAll("[data-kind]").forEach((b)=> b.onclick = async () => {
    const { markdown, error } = await api.get(`/api/audits/${id}/report/${b.dataset.kind}`);
    document.getElementById("report-out").textContent = error ? "ত্রুটি: "+error : markdown;
  });
  body.querySelectorAll("[data-export]").forEach((b)=> b.onclick = () => {
    const url = `/api/audits/${id}/export/${b.dataset.export}`;
    if (b.dataset.export === "pdf") window.open(url, "_blank"); // print-ready page
    else window.location.href = url; // download
  });
}

async function renderSettings(body) {
  const [s, providers] = await Promise.all([api.get("/api/settings"), api.get("/api/providers")]);
  body.innerHTML = `
    <div class="card" style="max-width:640px">
      <h3>AI বিশ্লেষণ Provider</h3>
      <label>Provider
        <select id="s-provider">${providers.map((p)=>`<option value="${p.id}" ${s.aiProvider===p.id?"selected":""}>${esc(p.label)}</option>`).join("")}</select>
      </label>
      <fieldset style="border:1px solid var(--line);border-radius:8px;padding:10px;margin-top:12px">
        <legend class="muted">Ollama (লোকাল, অফলাইন)</legend>
        <label>Base URL<input id="s-ollama-url" value="${esc(s.ollama.baseUrl)}" /></label>
        <label>Model<input id="s-ollama-model" value="${esc(s.ollama.model)}" placeholder="যেমন: llama3.1" /></label>
        <div class="hint">Ollama ইনস্টল ও চালু থাকতে হবে (ollama serve; ollama pull &lt;model&gt;)।</div>
      </fieldset>
      <fieldset style="border:1px solid var(--line);border-radius:8px;padding:10px;margin-top:12px">
        <legend class="muted">Claude API (অনলাইন)</legend>
        <label>Model<input id="s-claude-model" value="${esc(s.claude.model)}" /></label>
        <label>API Key ${s.claude.apiKeySet?'<span class="pill">সেট আছে ✓</span>':""}
          <input id="s-claude-key" type="password" placeholder="${s.claude.apiKeySet?"পরিবর্তন করতে নতুন key দিন":"sk-ant-..."}" /></label>
        <div class="hint">⚠️ Claude বেছে নিলে OCR টেক্সট ইন্টারনেটে API-তে যাবে (নথির ছবি নয়)।</div>
      </fieldset>
      <div class="row-end"><button class="btn btn-primary" id="s-save">সংরক্ষণ</button></div>
    </div>`;
  document.getElementById("s-save").onclick = async () => {
    const patch = {
      aiProvider: document.getElementById("s-provider").value,
      ollama: { baseUrl: document.getElementById("s-ollama-url").value, model: document.getElementById("s-ollama-model").value },
      claude: { model: document.getElementById("s-claude-model").value, apiKey: document.getElementById("s-claude-key").value },
    };
    await api.send("PUT", "/api/settings", patch);
    const btn = document.getElementById("s-save"); btn.textContent = "✓ সংরক্ষিত"; setTimeout(()=>btn.textContent="সংরক্ষণ",1500);
  };
}

// ---------- helpers ----------
function fileToBase64(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(",")[1]);
    r.onerror = rej;
    r.readAsDataURL(file);
  });
}

// ---------- boot ----------
document.getElementById("home-btn").onclick = viewHome;
(async function boot() {
  MODULES = await api.get("/api/modules");
  await refreshOcrBadge();
  await viewHome();
})();
