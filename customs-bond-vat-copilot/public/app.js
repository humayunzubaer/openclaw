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
      ${["dashboard","documents","findings","numeric","validity","working-paper","reports","settings"].map((t)=>
        `<div class="tab ${t===tab?"active":""}" data-tab="${t}">${tabLabel(t)}</div>`).join("")}
    </div>
    <div id="tab-body"><div class="loading">লোড হচ্ছে…</div></div>`;

  document.querySelectorAll("#tabs .tab").forEach((el)=> el.onclick = ()=> viewAudit(id, el.dataset.tab));

  const body = document.getElementById("tab-body");
  if (tab === "dashboard") return renderDashboard(body, id, module);
  if (tab === "documents") return renderDocuments(body, id, module);
  if (tab === "findings") return renderFindings(body, id, module);
  if (tab === "numeric") return renderNumeric(body, id, module);
  if (tab === "validity") return renderValidity(body, id, module);
  if (tab === "working-paper") return renderWorkingPaper(body, id, module);
  if (tab === "reports") return renderReports(body, id);
  if (tab === "settings") return renderSettings(body);
}

const tabLabel = (t) => ({ dashboard:"📊 ড্যাশবোর্ড", documents:"📁 নথি", findings:"🔍 Findings", numeric:"🧮 সংখ্যাগত যাচাই", validity:"📅 মেয়াদ যাচাই", "working-paper":"📝 Working Paper", reports:"📄 রিপোর্ট", settings:"⚙️ সেটিংস" }[t]);

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
  const [findings, documents] = await Promise.all([
    api.get(`/api/audits/${id}/findings`),
    api.get(`/api/audits/${id}/documents`),
  ]);
  const redo = () => renderFindings(body, id, module);
  body.innerHTML = `
    <div class="row" style="justify-content:space-between;margin-bottom:14px">
      <h3 style="margin:0">Findings (${findings.length})</h3>
      <div class="row">
        <button class="btn btn-ghost" id="ai-draft">🤖 খসড়া তৈরি</button>
        <button class="btn btn-primary" id="add-finding">+ Finding যোগ</button>
      </div>
    </div>
    <div id="find-list">${findings.length?findings.map((f)=>findingRow(f)).join(""):`<div class="empty">কোনো finding নেই। checklist থেকে খসড়া তৈরি করুন বা ম্যানুয়ালি যোগ করুন।</div>`}</div>`;

  document.getElementById("add-finding").onclick = () => addOrEditFinding(id, module, null, redo, documents);
  document.getElementById("ai-draft").onclick = async () => {
    if (!confirm("সেটিংসে নির্বাচিত provider দিয়ে খসড়া findings তৈরি হবে। এগুলো সম্পাদনাযোগ্য। এগিয়ে যাবেন?")) return;
    const r = await api.send("POST", `/api/audits/${id}/analyze`, {});
    if (r.error) return alert("বিশ্লেষণ ব্যর্থ: " + (r.message || r.error));
    for (const d of r.drafts) await api.send("POST", `/api/audits/${id}/findings`, d);
    redo();
  };
  body.querySelectorAll(".finding-item").forEach((el) => {
    const fid = el.dataset.find;
    el.querySelector(".act-edit").onclick = () => addOrEditFinding(id, module, findings.find((f)=>f.id===fid), redo, documents);
    el.querySelector(".act-del").onclick = async () => { if(confirm("মুছে ফেলবেন?")){ await api.send("DELETE", `/api/audits/${id}/findings/${fid}`); redo();} };
  });
}

function evidenceChips(f) {
  const ev = f.evidence ?? [];
  if (!ev.length) return "";
  return `<div class="row" style="flex-wrap:wrap;gap:4px;margin-top:6px">${ev.map((e) =>
    `<span class="prov-badge" title="উৎস: ${esc(e.sourceText || "")}">📄 ${esc(e.docFilename || "নথি")}${e.page != null ? ` · পৃ.${e.page}` : ""}${e.confidence != null ? ` · ${Math.round(e.confidence * 100)}%` : ""}</span>`).join("")}</div>`;
}

function findingRow(f) {
  return `<div class="finding-item ${esc(f.severity)}" data-find="${f.id}">
    <div class="row" style="justify-content:space-between">
      <strong>${esc(f.title || f.area)}</strong>
      <div class="row"><span class="pill">${esc(f.area)}</span>
        ${f.source && f.source !== "manual" ? `<span class="pill">${esc(f.source)}</span>` : ""}
        <button class="btn btn-ghost btn-sm act-edit">সম্পাদনা</button>
        <button class="btn btn-ghost btn-sm act-del">মুছুন</button></div>
    </div>
    <div style="margin-top:6px">${esc(f.observation)}</div>
    <div class="row muted" style="margin-top:6px;font-size:13px">
      ${f.legalRef?`আইন: ${esc(f.legalRef)} · `:""}রাজস্ব: ৳${bdt(f.revenueImplication)} · severity: ${esc(f.severity)}</div>
    ${evidenceChips(f)}
  </div>`;
}

function addOrEditFinding(id, module, existing, done, documents = []) {
  const areas = [...new Set(module.checklist.map((c)=>c.area))];
  const legalOpts = [...new Set(module.checklist.map((c)=>c.legalRef).filter(Boolean))];
  let evidence = (existing?.evidence ?? []).map((e) => ({ ...e }));
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
    <div class="ev-section">
      <strong style="font-size:13px">Evidence — নথি + পৃষ্ঠা</strong>
      <div id="ev-list" style="margin:6px 0"></div>
      ${documents.length ? `<div class="row" style="gap:6px;flex-wrap:wrap">
        <select id="ev-doc" style="flex:2;min-width:180px">${documents.map((d,i)=>`<option value="${i}">${esc(d.filename)}</option>`).join("")}</select>
        <input id="ev-page" type="number" min="1" placeholder="পৃষ্ঠা" style="max-width:90px" />
        <button type="button" class="btn btn-ghost btn-sm" id="ev-add">＋ যোগ</button>
      </div>
      <input id="ev-src" placeholder="উৎস টেক্সট (ঐচ্ছিক)" style="margin-top:6px" />`
        : `<div class="muted" style="font-size:12.5px">নথি নেই — "📁 নথি" ট্যাবে আপলোড করলে এখানে যুক্ত করা যাবে।</div>`}
    </div>
    <div class="row-end"><button type="button" class="btn btn-ghost" id="fc">বাতিল</button><button class="btn btn-primary">সংরক্ষণ</button></div>
  </form>`;
  document.body.appendChild(dlg); dlg.showModal();

  const evList = dlg.querySelector("#ev-list");
  const renderEv = () => {
    evList.innerHTML = evidence.length
      ? evidence.map((e, i) => `<div class="row" style="justify-content:space-between;gap:6px;border:1px solid var(--line);border-radius:6px;padding:4px 8px;margin-bottom:4px">
          <span style="font-size:12.5px">📄 ${esc(e.docFilename || "নথি")}${e.page != null ? ` · পৃ.${e.page}` : ""}${e.confidence != null ? ` · ${Math.round(e.confidence*100)}%` : ""}</span>
          <button type="button" class="btn btn-ghost btn-sm ev-rm" data-i="${i}">✕</button></div>`).join("")
      : `<div class="muted" style="font-size:12px">এখনো কোনো evidence যুক্ত নেই।</div>`;
    evList.querySelectorAll(".ev-rm").forEach((b) => b.onclick = () => { evidence.splice(Number(b.dataset.i), 1); renderEv(); });
  };
  renderEv();

  if (documents.length) {
    dlg.querySelector("#ev-add").onclick = () => {
      const d = documents[Number(dlg.querySelector("#ev-doc").value)];
      const pageRaw = dlg.querySelector("#ev-page").value;
      const src = dlg.querySelector("#ev-src").value;
      if (!d) return;
      evidence.push({ docId: d.id, docFilename: d.filename, page: pageRaw === "" ? null : Number(pageRaw), sourceText: src });
      dlg.querySelector("#ev-page").value = ""; dlg.querySelector("#ev-src").value = "";
      renderEv();
    };
  }

  dlg.querySelector("#fc").onclick = () => { dlg.close(); dlg.remove(); };
  dlg.querySelector("form").onsubmit = async () => {
    const data = Object.fromEntries(new FormData(dlg.querySelector("form")));
    data.revenueImplication = Number(data.revenueImplication) || 0;
    data.evidence = evidence;
    if (existing) await api.send("PATCH", `/api/audits/${id}/findings/${existing.id}`, data);
    else await api.send("POST", `/api/audits/${id}/findings`, data);
    dlg.close(); dlg.remove(); done();
  };
}

// ---------- Numeric auto-check ----------
const SEV = { high: { l: "গুরুতর", c: "var(--high)" }, medium: { l: "মাঝারি", c: "var(--med,#b8860b)" }, low: { l: "স্বাভাবিক", c: "var(--ok,#2e7d32)" } };

async function renderNumeric(body, id, module) {
  const [data, evidence] = await Promise.all([
    api.get(`/api/audits/${id}/numeric`),
    api.get(`/api/audits/${id}/evidence`),
  ]);
  const specs = data.specs || [];
  const inputs = data.inputs || {};
  let results = data.results || [];
  let applied = evidence.applied || {};
  const resById = () => Object.fromEntries(results.map((r) => [r.id, r]));
  const provKey = (cid, key) => `${cid}::${key}`;
  const flatFields = specs.flatMap((s) => s.inputs.map((inp) => ({ checkId: s.id, checkTitle: s.title, inputKey: inp.key, inputLabel: inp.label })));

  if (!specs.length) {
    body.innerHTML = `<div class="empty">এই মডিউলে সংখ্যাগত check নেই।</div>`;
    return;
  }

  const cards = specs.map((s) => {
    const saved = inputs[s.id] || {};
    const fields = s.inputs.map((inp) => `
      <label class="num-field">${esc(inp.label)}${inp.unit ? ` <span class="muted">(${esc(inp.unit)})</span>` : ""}${inp.optional ? ' <span class="muted">— ঐচ্ছিক</span>' : ""}
        <input type="number" step="any" inputmode="decimal" data-check="${s.id}" data-key="${inp.key}" value="${saved[inp.key] ?? ""}" />
        <div class="prov" data-prov="${s.id}::${inp.key}"></div>
      </label>`).join("");
    return `<div class="card num-card" data-check="${s.id}">
      <div class="row" style="justify-content:space-between;align-items:flex-start">
        <div><strong>${esc(s.title)}</strong><div class="muted" style="font-size:12.5px;margin-top:2px">${esc(s.area)} · ${esc(s.formula || "")}</div></div>
        <button class="btn btn-ghost btn-sm act-promote" title="Finding হিসেবে যোগ">➕ Finding</button>
      </div>
      <div class="num-grid">${fields}</div>
      <div class="num-result" data-result="${s.id}"></div>
    </div>`;
  }).join("");

  body.innerHTML = `
    <div class="row" style="justify-content:space-between;margin-bottom:12px">
      <div><h3 style="margin:0">🧮 সংখ্যাগত যাচাই</h3><div class="muted" style="font-size:13px">সংখ্যা বসান → হিসাব করুন। ব্যত্যয় পেলে "Finding" চেপে চূড়ান্ত রিপোর্টে নিন।</div></div>
      <div class="row">
        <button class="btn btn-ghost" id="num-evidence">🔍 নথি থেকে Evidence</button>
        <button class="btn btn-ghost" id="num-trail">🧾 Trail</button>
        <button class="btn btn-ghost" id="num-promote-all">flag → Findings</button>
        <button class="btn btn-primary" id="num-compute">হিসাব করুন</button>
      </div>
    </div>
    <div id="num-summary"></div>
    <div class="grid">${cards}</div>`;

  const renderResults = () => {
    const map = resById();
    body.querySelectorAll(".num-result").forEach((el) => {
      const r = map[el.dataset.result];
      if (!r || r.status === "insufficient") { el.innerHTML = r?.status === "insufficient" ? `<div class="muted" style="font-size:12.5px">${esc(r.observation)}</div>` : ""; return; }
      const sev = SEV[r.severity] || SEV.low;
      const badge = r.status === "flag" ? `<span class="pill" style="background:${sev.c};color:#fff">⚠ ${sev.l}</span>` : `<span class="pill" style="background:var(--ok,#2e7d32);color:#fff">✓ ব্যত্যয় নেই</span>`;
      const rev = r.status === "flag" && Number(r.revenueImplication) ? ` · রাজস্ব: ৳${bdt(r.revenueImplication)}` : "";
      el.innerHTML = `<div class="num-out ${r.status}">${badge}${rev}<div style="margin-top:4px">${esc(r.observation)}</div></div>`;
    });
    const flagged = results.filter((r) => r.status === "flag");
    const subtotal = flagged.reduce((s, r) => s + Number(r.revenueImplication || 0), 0);
    document.getElementById("num-summary").innerHTML = results.length
      ? `<div class="stat-row"><div class="stat"><div class="n" style="color:var(--high)">${flagged.length}</div><div class="l">ব্যত্যয় চিহ্নিত</div></div>
         <div class="stat"><div class="n">৳${bdt(subtotal)}</div><div class="l">সম্ভাব্য রাজস্ব (উপমোট)</div></div></div>`
      : "";
  };

  const renderProvenance = () => {
    body.querySelectorAll(".prov").forEach((el) => {
      const pv = applied[el.dataset.prov];
      el.innerHTML = pv
        ? `<span class="prov-badge" title="উৎস: ${esc(pv.sourceText)}">📄 ${esc(pv.docFilename || "?")} · পৃ.${pv.page ?? "?"} · ${Math.round((pv.confidence ?? 0) * 100)}%</span>`
        : "";
    });
  };
  renderResults();
  renderProvenance();

  const collectInputs = () => {
    const out = {};
    body.querySelectorAll("input[data-check]").forEach((el) => {
      const cid = el.dataset.check, key = el.dataset.key;
      if (el.value === "") return;
      (out[cid] ??= {})[key] = el.value;
    });
    return out;
  };

  document.getElementById("num-compute").onclick = async () => {
    const btn = document.getElementById("num-compute");
    btn.textContent = "হিসাব হচ্ছে…"; btn.disabled = true;
    const r = await api.send("POST", `/api/audits/${id}/numeric`, { inputs: collectInputs() });
    results = r.results || [];
    const ev = await api.get(`/api/audits/${id}/evidence`); // manual override → provenance prune reflect
    applied = ev.applied || {};
    renderResults();
    renderProvenance();
    btn.textContent = "✓ হিসাব হয়েছে"; setTimeout(() => { btn.textContent = "হিসাব করুন"; btn.disabled = false; }, 1200);
  };

  const applyChip = async (chip, checkId, inputKey) => {
    const resp = await api.send("POST", `/api/audits/${id}/evidence/apply`, { chip, checkId, inputKey });
    if (resp.error) { alert("প্রয়োগ ব্যর্থ: " + resp.error); return false; }
    const inp = body.querySelector(`input[data-check="${checkId}"][data-key="${inputKey}"]`);
    if (inp) inp.value = chip.value;
    applied[provKey(checkId, inputKey)] = resp.applied;
    results = resp.numeric.results;
    renderResults();
    renderProvenance();
    return true;
  };

  const fieldOptions = (selKey) =>
    flatFields.map((f) => `<option value="${f.checkId}::${f.inputKey}" ${selKey === `${f.checkId}::${f.inputKey}` ? "selected" : ""}>${esc(f.checkTitle)} → ${esc(f.inputLabel)}</option>`).join("");

  document.getElementById("num-evidence").onclick = async () => {
    const dlg = document.createElement("dialog");
    dlg.className = "evi-dialog";
    dlg.innerHTML = `<div class="row" style="justify-content:space-between"><h3 style="margin:0">🔍 নথি থেকে Smart Evidence</h3><button class="btn btn-ghost btn-sm" id="evi-close">বন্ধ</button></div>
      <div class="muted" style="font-size:13px;margin:6px 0 12px">OCR-করা নথি থেকে সংখ্যা তোলা হলো — প্রতিটি chip-এ document, পৃষ্ঠা, source টেক্সট, field-সাজেশন ও confidence আছে। সঠিক field বেছে "প্রয়োগ" চাপুন।</div>
      <div id="evi-body"><div class="loading">স্ক্যান হচ্ছে…</div></div>`;
    document.body.appendChild(dlg); dlg.showModal();
    dlg.querySelector("#evi-close").onclick = () => { dlg.close(); dlg.remove(); };
    const scan = await api.send("POST", `/api/audits/${id}/evidence/scan`, {});
    const eb = dlg.querySelector("#evi-body");
    if (!scan.totalChips) {
      eb.innerHTML = `<div class="empty">OCR-করা নথিতে কোনো সংখ্যা পাওয়া যায়নি। আগে "📁 নথি" ট্যাবে OCR চালান।</div>`;
      return;
    }
    const chipMap = {};
    for (const g of scan.groups) chipMap[g.docId] = g.chips;
    eb.innerHTML = scan.groups.map((g) => `
      <div class="evi-group"><div class="evi-doc">📄 ${esc(g.filename)} <span class="muted">(${g.chips.length}টি সংখ্যা)</span></div>
      ${g.chips.map((c, i) => {
        const top = c.suggestions[0];
        const conf = Math.round(c.confidence * 100);
        const cc = conf >= 70 ? "var(--ok)" : conf >= 40 ? "var(--med,#b8860b)" : "var(--high)";
        return `<div class="evi-chip" data-gi="${esc(g.docId)}" data-ci="${i}">
          <div class="row" style="justify-content:space-between;align-items:flex-start">
            <div><span class="evi-val">${bdt(c.value)}</span> <span class="muted">পৃ.${c.page}</span></div>
            <span class="evi-conf" style="color:${cc}">confidence ${conf}%</span>
          </div>
          <div class="evi-src muted">“${esc(c.sourceText)}”</div>
          <div class="row" style="margin-top:6px;gap:6px">
            <select class="evi-field">${fieldOptions(top ? `${top.checkId}::${top.inputKey}` : "")}</select>
            <button class="btn btn-primary btn-sm evi-apply">প্রয়োগ</button>
          </div></div>`;
      }).join("")}</div>`).join("");
    eb.querySelectorAll(".evi-chip").forEach((el) => {
      el.querySelector(".evi-apply").onclick = async (e) => {
        const chip = chipMap[el.dataset.gi][Number(el.dataset.ci)];
        const [checkId, inputKey] = el.querySelector(".evi-field").value.split("::");
        e.target.textContent = "…"; e.target.disabled = true;
        const okApply = await applyChip(chip, checkId, inputKey);
        e.target.textContent = okApply ? "✓ প্রয়োগ হয়েছে" : "প্রয়োগ";
        e.target.disabled = okApply;
      };
    });
  };

  document.getElementById("num-trail").onclick = async () => {
    const ev = await api.get(`/api/audits/${id}/evidence`);
    const dlg = document.createElement("dialog");
    dlg.className = "evi-dialog";
    const rows = (ev.log || []).slice().reverse().map((l) => `<tr>
      <td>${l.appliedAt ? new Date(l.appliedAt).toLocaleString("en-CA") : "—"}</td>
      <td>${esc(l.action)}${l.prevValue != null ? ` <span class="muted">(আগে ${bdt(l.prevValue)})</span>` : ""}</td>
      <td>${esc(l.checkTitle || "")} → ${esc(l.inputLabel || "")}</td>
      <td style="text-align:right">${bdt(l.value)}</td>
      <td>${esc(l.docFilename || "—")} পৃ.${l.page ?? "—"}</td>
      <td>${esc(l.auditor || "—")}</td></tr>`).join("");
    dlg.innerHTML = `<div class="row" style="justify-content:space-between"><h3 style="margin:0">🧾 Evidence audit trail</h3><button class="btn btn-ghost btn-sm" id="tr-close">বন্ধ</button></div>
      ${rows ? `<div style="overflow:auto;margin-top:10px"><table class="evi-trail"><thead><tr><th>সময়</th><th>action</th><th>field</th><th>মান</th><th>উৎস</th><th>নিরীক্ষক</th></tr></thead><tbody>${rows}</tbody></table></div>` : `<div class="empty">এখনো কোনো evidence প্রয়োগ হয়নি।</div>`}`;
    document.body.appendChild(dlg); dlg.showModal();
    dlg.querySelector("#tr-close").onclick = () => { dlg.close(); dlg.remove(); };
  };

  document.getElementById("num-promote-all").onclick = async () => {
    if (!results.some((r) => r.status === "flag")) return alert("আগে হিসাব করুন — কোনো flag পাওয়া যায়নি।");
    if (!confirm("সব flag হওয়া check Finding হিসেবে যোগ হবে (ডুপ্লিকেট বাদ)। এগিয়ে যাবেন?")) return;
    const r = await api.send("POST", `/api/audits/${id}/numeric/to-findings`, {});
    alert(`${r.added}টি Finding যোগ হয়েছে${r.skipped ? `, ${r.skipped}টি আগে থেকেই ছিল` : ""}।`);
  };

  body.querySelectorAll(".num-card").forEach((card) => {
    card.querySelector(".act-promote").onclick = async () => {
      const cid = card.dataset.check;
      const r = resById()[cid];
      if (!r || r.status !== "flag") return alert("এই check-এ কোনো ব্যত্যয় নেই (আগে হিসাব করুন)।");
      const resp = await api.send("POST", `/api/audits/${id}/numeric/to-findings`, { checkIds: [cid] });
      alert(resp.added ? "Finding হিসেবে যোগ হয়েছে।" : "আগে থেকেই যোগ করা আছে।");
    };
  });
}

// ---------- Validity (মেয়াদ/Entitlement) ----------
async function renderValidity(body, id, module) {
  const data = await api.get(`/api/audits/${id}/validity`);
  const specs = data.specs || [];
  const inputs = data.inputs || {};
  let results = data.results || [];
  const resById = () => Object.fromEntries(results.map((r) => [r.id, r]));

  if (!specs.length) { body.innerHTML = `<div class="empty">এই মডিউলে মেয়াদ-যাচাই নেই।</div>`; return; }

  const cards = specs.map((s) => {
    const saved = inputs[s.id] || {};
    const fields = s.inputs.map((inp) => `
      <label class="num-field">${esc(inp.label)}${inp.optional ? ' <span class="muted">— ঐচ্ছিক</span>' : ""}
        <input type="${inp.type === "date" ? "date" : "text"}" data-check="${s.id}" data-key="${inp.key}" value="${esc(saved[inp.key] ?? "")}" ${inp.type === "text" ? `placeholder="যেমন: 5208.11, 6109.10"` : ""} />
      </label>`).join("");
    return `<div class="card num-card" data-check="${s.id}">
      <div class="row" style="justify-content:space-between;align-items:flex-start">
        <div><strong>${esc(s.title)}</strong><div class="muted" style="font-size:12.5px;margin-top:2px">${esc(s.area)} · ${esc(s.formula || "")}</div></div>
        <button class="btn btn-ghost btn-sm act-promote" title="Finding হিসেবে যোগ">➕ Finding</button>
      </div>
      <div class="num-grid">${fields}</div>
      <div class="num-result" data-result="${s.id}"></div>
    </div>`;
  }).join("");

  body.innerHTML = `
    <div class="row" style="justify-content:space-between;margin-bottom:12px">
      <div><h3 style="margin:0">📅 মেয়াদ / Entitlement যাচাই</h3><div class="muted" style="font-size:13px">তারিখ ও HS code বসান → যাচাই করুন। ব্যত্যয় পেলে "Finding" চেপে রিপোর্টে নিন।</div></div>
      <div class="row">
        <button class="btn btn-ghost" id="val-promote-all">flag → Findings</button>
        <button class="btn btn-primary" id="val-check">যাচাই করুন</button>
      </div>
    </div>
    <div id="val-summary"></div>
    <div class="grid">${cards}</div>`;

  const renderResults = () => {
    const map = resById();
    body.querySelectorAll(".num-result").forEach((el) => {
      const r = map[el.dataset.result];
      if (!r || r.status === "insufficient") { el.innerHTML = r?.status === "insufficient" ? `<div class="muted" style="font-size:12.5px">${esc(r.observation)}</div>` : ""; return; }
      const sev = SEV[r.severity] || SEV.low;
      const badge = r.status === "flag" ? `<span class="pill" style="background:${sev.c};color:#fff">⚠ ${sev.l}</span>` : `<span class="pill" style="background:var(--ok,#2e7d32);color:#fff">✓ ঠিক আছে</span>`;
      el.innerHTML = `<div class="num-out ${r.status}">${badge}<div style="margin-top:4px">${esc(r.observation)}</div></div>`;
    });
    const flagged = results.filter((r) => r.status === "flag");
    document.getElementById("val-summary").innerHTML = results.length
      ? `<div class="stat-row"><div class="stat"><div class="n" style="color:var(--high)">${flagged.length}</div><div class="l">মেয়াদ/entitlement ব্যত্যয়</div></div></div>`
      : "";
  };
  renderResults();

  const collectInputs = () => {
    const out = {};
    body.querySelectorAll("input[data-check]").forEach((el) => {
      if (el.value === "") return;
      (out[el.dataset.check] ??= {})[el.dataset.key] = el.value;
    });
    return out;
  };

  document.getElementById("val-check").onclick = async () => {
    const btn = document.getElementById("val-check");
    btn.textContent = "যাচাই হচ্ছে…"; btn.disabled = true;
    const r = await api.send("POST", `/api/audits/${id}/validity`, { inputs: collectInputs() });
    results = r.results || [];
    renderResults();
    btn.textContent = "✓ যাচাই হয়েছে"; setTimeout(() => { btn.textContent = "যাচাই করুন"; btn.disabled = false; }, 1200);
  };

  document.getElementById("val-promote-all").onclick = async () => {
    if (!results.some((r) => r.status === "flag")) return alert("আগে যাচাই করুন — কোনো flag পাওয়া যায়নি।");
    if (!confirm("সব flag হওয়া যাচাই Finding হিসেবে যোগ হবে (ডুপ্লিকেট বাদ)। এগিয়ে যাবেন?")) return;
    const r = await api.send("POST", `/api/audits/${id}/validity/to-findings`, {});
    alert(`${r.added}টি Finding যোগ হয়েছে${r.skipped ? `, ${r.skipped}টি আগে থেকেই ছিল` : ""}।`);
  };

  body.querySelectorAll(".num-card").forEach((card) => {
    card.querySelector(".act-promote").onclick = async () => {
      const cid = card.dataset.check;
      const r = resById()[cid];
      if (!r || r.status !== "flag") return alert("এই যাচাইয়ে কোনো ব্যত্যয় নেই (আগে যাচাই করুন)।");
      const resp = await api.send("POST", `/api/audits/${id}/validity/to-findings`, { checkIds: [cid] });
      alert(resp.added ? "Finding হিসেবে যোগ হয়েছে।" : "আগে থেকেই যোগ করা আছে।");
    };
  });
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

// অ্যাপ-জুড়ে global সেটিংস পর্দা (অডিট না খুলেই)
async function viewSettings() {
  app.innerHTML = `
    <div class="section-head"><h2>⚙️ সেটিংস</h2></div>
    <p class="muted">এই সেটিংস সব অডিটে প্রযোজ্য (app-wide)। একবার সেট করলেই যথেষ্ট।</p>
    <div id="settings-body"></div>`;
  renderSettings(document.getElementById("settings-body"));
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
document.getElementById("settings-btn").onclick = viewSettings;
(async function boot() {
  MODULES = await api.get("/api/modules");
  await refreshOcrBadge();
  await viewHome();
})();
