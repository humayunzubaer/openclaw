// Import Intelligence — frontend (vanilla JS, no build)

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const money = (n) => "৳ " + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const num = (n) => Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 3 });
const bdt = (n) => Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });

// JSON fetch helper (ম্যানুয়াল-যাচাই view ব্যবহার করে)
const api = {
  async get(url) { return (await fetch(url)).json(); },
  async send(method, url, body) {
    const r = await fetch(url, { method, headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined });
    return r.json();
  },
};

// ---------- health ----------
(async () => {
  const b = $("health");
  try {
    const r = await fetch("/api/health");
    const j = await r.json();
    b.textContent = "সংযুক্ত · v" + j.version;
    b.className = "badge badge-ok";
  } catch {
    b.textContent = "সার্ভার বন্ধ";
    b.className = "badge badge-off";
  }
})();

// ---------- form ----------
function buildForm() {
  const ent = $("ent").files[0], imp = $("imp").files[0], local = $("local").files[0];
  const register = $("register").files[0];
  if (!ent || !imp) {
    setMsg("প্রাপ্যতা শীট ও আমদানি ফাইল — দুটোই দিন।", "err");
    return null;
  }
  const fd = new FormData();
  fd.append("entitlement_file", ent);
  fd.append("imports_file", imp);
  if (local) fd.append("local_file", local);
  if (register) fd.append("register_file", register);
  if ($("nxt").value) fd.append("next_entitlement_date", $("nxt").value);
  fd.append("bond_license_capacity_mt", $("lic").value || "0");
  fd.append("warehouse_capacity_mt", $("wh").value || "0");
  fd.append("extension_applies", $("ext").checked ? "true" : "false");
  return fd;
}

function setMsg(t, cls = "") { const m = $("msg"); m.textContent = t; m.className = "msg " + cls; }
function busy(on) { $("run").disabled = on; $("xlsx").disabled = on; }

$("run").onclick = async () => {
  const fd = buildForm();
  if (!fd) return;
  busy(true); setMsg("বিশ্লেষণ চলছে…");
  try {
    const r = await fetch("/api/analyze/import", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || "বিশ্লেষণ ব্যর্থ");
    render(j);
    setMsg("বিশ্লেষণ সম্পন্ন।", "ok");
  } catch (e) {
    setMsg("ত্রুটি: " + e.message, "err");
  } finally { busy(false); }
};

$("xlsx").onclick = async () => {
  const fd = buildForm();
  if (!fd) return;
  busy(true); setMsg("কার্যপত্র তৈরি হচ্ছে…");
  try {
    const r = await fetch("/api/analyze/import/xlsx", { method: "POST", body: fd });
    if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error(j.detail || "কার্যপত্র ব্যর্থ"); }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "audit_workpaper.xlsx"; a.click();
    URL.revokeObjectURL(url);
    setMsg("কার্যপত্র ডাউনলোড হয়েছে।", "ok");
  } catch (e) {
    setMsg("ত্রুটি: " + e.message, "err");
  } finally { busy(false); }
};

// ---------- render ----------
const CLAIM_KEYS = [
  ["দাবি ১ — অননুমোদিত এইচএস কোড (BDT)", "অননুমোদিত HS"],
  ["দাবি ২ — প্রাপ্যতার অতিরিক্ত আমদানি (BDT)", "অতিরিক্ত আমদানি"],
  ["দাবি ৩ — বন্ডিং ক্যাপাসিটির অতিরিক্ত (BDT)", "বন্ডিং ক্যাপাসিটি"],
  ["দাবি ৪ — উৎপাদন ক্ষমতার ৮০% সীমা লঙ্ঘন [বিধি ১১(১)] (BDT)", "৮০% সীমা [১১(১)]"],
  ["দাবি ৫ — মেয়াদ সমাপনান্তে প্রাপ্যতা ব্যতীত আমদানি (BDT)", "মেয়াদোত্তর আমদানি"],
];

function render(j) {
  $("out").classList.remove("hidden");
  const s = j.summary || {};

  // stats
  $("stats").innerHTML = CLAIM_KEYS.map(([k, label]) => {
    const v = Number(s[k] || 0);
    return `<div class="stat ${v > 0 ? "high" : ""}"><div class="n">${money(v)}</div><div class="l">${label}</div></div>`;
  }).join("");

  const grand = Number(s["সর্বমোট রাজস্ব দাবি (BDT)"] || 0);
  $("grandtotal").textContent = "সর্বমোট রাজস্ব দাবি: " + money(grand);

  // warnings
  const w = j.warnings || [];
  $("warnings").innerHTML = w.length ? w.map((x) => `<li>${esc(x)}</li>`).join("") : `<li class="empty">কোনো সতর্কতা নেই।</li>`;

  // বিধি ৮ — বর্ধিত প্রাপ্যতা পর্যবেক্ষণ (দাবি নহে)
  const r8 = (j.records && j.records.rule8) || [];
  const r8box = $("rule8");
  if (r8.length) {
    const overall = r8.find((o) => o.scope === "overall");
    const items = r8.filter((o) => o.scope === "item");
    const itemRows = items.length ? `<div class="tablewrap"><table><thead><tr>
        <th>#</th><th>প্রাপ্যতা আইটেম</th><th class="num">মূল</th><th class="num">বর্ধিত [বিধি ৮]</th>
        <th class="num">মোট অনুমোদিত</th><th>একক</th></tr></thead><tbody>${
        items.map((o) => `<tr><td>${o.serial}</td><td>${esc(o.entitlement_item)}</td>
          <td class="num">${num(o.base_entitlement)}</td><td class="num">${num(o.extended_entitlement)}</td>
          <td class="num">${num(o.combined_entitlement)}</td><td>${esc(o.unit)}</td></tr>`).join("")
        }</tbody></table></div>` : "";
    r8box.innerHTML = `<div class="card">
      <h2>৩ক. বিধি ৮ — বর্ধিত প্রাপ্যতা ও বিয়োজন যাচাই <small>(পর্যবেক্ষণ, দাবি নহে)</small></h2>
      <div class="warnbox">${esc(overall ? overall.instruction : "")}</div>
      ${itemRows}
      <div class="muted" style="margin-top:8px;font-size:12.5px">আইনি ভিত্তি: ${esc(overall ? overall.legal_basis : "")}</div>
    </div>`;
  } else {
    r8box.innerHTML = "";
  }

  // tables
  const rec = j.records || {};
  const tables = [
    ["অতিরিক্ত আমদানি (দাবি ২)", rec.excess, [
      ["serial", "#"], ["entitlement_item", "প্রাপ্যতা আইটেম"], ["entitled_quantity", "প্রাপ্যতা", 1],
      ["imported_quantity", "আমদানি", 1], ["excess_quantity", "অতিরিক্ত", 1], ["unit", "একক"],
      ["total_revenue_impact", "দাবি (৳)", 2],
    ]],
    ["অননুমোদিত এইচএস কোড (দাবি ১)", rec.unauthorized, [
      ["serial", "#"], ["hs_code", "HS"], ["item_name", "পণ্য"], ["bill_count", "বিল", 1],
      ["total_quantity", "পরিমাণ", 1], ["unit", "একক"], ["total_revenue_impact", "দাবি (৳)", 2],
    ]],
    ["মেয়াদোত্তর আমদানি (দাবি ৫)", rec.post_period, [
      ["serial", "#"], ["source", "উৎস"], ["hs_code", "HS"], ["item_name", "পণ্য"],
      ["bill_count", "বিল", 1], ["total_quantity", "পরিমাণ", 1], ["unit", "একক"],
      ["period_window", "সময়কাল"], ["total_revenue_impact", "দাবি (৳)", 2],
    ]],
    ["বন্ডিং ক্যাপাসিটি লঙ্ঘন (দাবি ৩)", rec.capacity_breach, null],
    ["উৎপাদন ক্ষমতার ৮০% সীমা (দাবি ৪)", rec.capacity_limit, null],
    ["প্রাপ্যতা ব্যবহার", rec.utilization, [
      ["serial", "#"], ["entitlement_item", "আইটেম"], ["entitled_quantity", "প্রাপ্যতা", 1],
      ["imported_quantity", "আমদানি", 1], ["balance_quantity", "উদ্বৃত্ত", 1],
      ["utilization_pct", "ব্যবহার %", 1], ["status", "অবস্থা"],
    ]],
  ];
  $("tables").innerHTML = tables.map(([title, rows, cols]) => tableCard(title, rows || [], cols)).join("");
}

function tableCard(title, rows, cols) {
  if (!rows.length) return `<div class="card"><h2>${esc(title)}</h2><div class="empty">কোনো রেকর্ড নেই।</div></div>`;
  if (!cols) cols = autoCols(rows[0]);
  const head = cols.map(([, label, n]) => `<th class="${n ? "num" : ""}">${esc(label)}</th>`).join("");
  const body = rows.map((r) => "<tr>" + cols.map(([key, , n]) => {
    let v = r[key];
    if (n === 2) v = money(v); else if (n === 1) v = num(v);
    return `<td class="${n ? "num" : ""}">${esc(v)}</td>`;
  }).join("") + "</tr>").join("");
  return `<div class="card"><h2>${esc(title)} <small>(${rows.length})</small></h2>
    <div class="tablewrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div></div>`;
}

// ---------- Manual checks view (numeric + validity + evidence) ----------
const SEV = { high: "var(--high)", medium: "var(--warn)", low: "var(--ok)" };
let SPECS = null;

function showView(which) {
  $("view-file").classList.toggle("hidden", which !== "file");
  $("view-manual").classList.toggle("hidden", which !== "manual");
  $("nav-file").className = "btn btn-sm " + (which === "file" ? "btn-primary" : "btn-ghost");
  $("nav-manual").className = "btn btn-sm " + (which === "manual" ? "btn-primary" : "btn-ghost");
  if (which === "manual") renderManual();
}
$("nav-file").onclick = () => showView("file");
$("nav-manual").onclick = () => showView("manual");

function checkCard(s, kind) {
  const fields = s.inputs.map((inp) => {
    const type = inp.type === "date" ? "date" : inp.type === "text" ? "text" : "number";
    const opt = inp.optional ? ' <span class="muted">— ঐচ্ছিক</span>' : "";
    const u = inp.unit ? ` <span class="muted">(${esc(inp.unit)})</span>` : "";
    return `<label class="num-field">${esc(inp.label)}${u}${opt}
      <input type="${type}" step="any" data-check="${s.id}" data-key="${inp.key}"
        ${type === "text" ? 'placeholder="5208.11, 6109.10"' : ""} /></label>`;
  }).join("");
  return `<div class="card num-card" data-check="${s.id}" data-kind="${kind}">
    <strong>${esc(s.title)}</strong>
    <div class="muted" style="font-size:12px;margin:2px 0 8px">${esc(s.area)} · ${esc(s.formula || "")}</div>
    <div class="num-grid">${fields}</div>
    <div class="num-result" data-result="${s.id}"></div></div>`;
}

async function renderManual() {
  const box = $("view-manual");
  if (!SPECS) SPECS = await api.get("/api/checks/specs");
  box.innerHTML = `
    <div class="card" style="margin-bottom:14px">
      <div class="muted" style="font-size:13px">নিরীক্ষক সংখ্যা/তারিখ বসিয়ে যাচাই করুন। এখানকার
      উপমোট চূড়ান্ত রাজস্ব-মোটে নিজে থেকে যোগ হয় না — এগুলো ফাইল-বিশ্লেষণের পরিপূরক পর্যবেক্ষণ।</div>
    </div>
    <div class="section-head"><h2>🧮 সংখ্যাগত যাচাই</h2>
      <button class="btn btn-primary btn-sm" id="run-num">হিসাব করুন</button></div>
    <div id="num-summary"></div>
    <div class="grid">${SPECS.numeric.map((s) => checkCard(s, "num")).join("")}</div>
    <div class="section-head" style="margin-top:20px"><h2>📅 মেয়াদ / Entitlement যাচাই</h2>
      <button class="btn btn-primary btn-sm" id="run-val">যাচাই করুন</button></div>
    <div id="val-summary"></div>
    <div class="grid">${SPECS.validity.map((s) => checkCard(s, "val")).join("")}</div>
    <div class="section-head" style="margin-top:20px"><h2>🔍 Smart Evidence (OCR টেক্সট → সংখ্যা)</h2></div>
    <div class="card">
      <div class="muted" style="font-size:12.5px;margin-bottom:6px">নথির OCR টেক্সট paste করুন — টুল সংখ্যা তুলে
      কোন check-input-এ বসতে পারে তার সাজেশন ও confidence দেখাবে (auto-map নয়)।</div>
      <textarea id="ev-text" style="width:100%;min-height:90px" placeholder="যেমন: মেশিনারিজ রেজিস্টার লিপিবদ্ধ 4 একক ..."></textarea>
      <div class="row-end"><button class="btn btn-ghost btn-sm" id="run-ev">Evidence তুলুন</button></div>
      <div id="ev-out"></div>
    </div>`;

  const collect = (kind) => {
    const inputs = {};
    box.querySelectorAll(`.num-card[data-kind="${kind}"] input[data-check]`).forEach((el) => {
      if (el.value === "") return;
      (inputs[el.dataset.check] ??= {})[el.dataset.key] = el.value;
    });
    return inputs;
  };
  const showResults = (results, sumSel, sumHtml) => {
    const map = Object.fromEntries(results.map((r) => [r.id, r]));
    box.querySelectorAll(".num-result").forEach((el) => {
      const r = map[el.dataset.result];
      if (!r || r.status === "insufficient") { el.innerHTML = r && r.status === "insufficient" ? `<div class="muted" style="font-size:12px">${esc(r.observation)}</div>` : ""; return; }
      const flag = r.status === "flag";
      const c = SEV[r.severity] || SEV.low;
      const rev = flag && Number(r.revenue_implication) ? ` · রাজস্ব: ৳${bdt(r.revenue_implication)}` : "";
      el.innerHTML = `<div class="num-out ${r.status}"><span class="pill" style="background:${c};color:#fff">${flag ? "⚠ " + r.severity : "✓ ঠিক"}</span>${rev}<div style="margin-top:4px">${esc(r.observation)}</div></div>`;
    });
    $(sumSel).innerHTML = sumHtml;
  };

  $("run-num").onclick = async () => {
    const r = await api.send("POST", "/api/checks/numeric", { inputs: collect("num") });
    showResults(r.results, "num-summary",
      `<div class="stat-row"><div class="stat"><div class="n" style="color:var(--high)">${r.summary.flagged}</div><div class="l">ব্যত্যয়</div></div>
       <div class="stat"><div class="n">৳${bdt(r.summary.totalRevenue)}</div><div class="l">উপমোট (গৃহীত হলে যোগ হবে)</div></div></div>`);
  };
  $("run-val").onclick = async () => {
    const r = await api.send("POST", "/api/checks/validity", { inputs: collect("val") });
    showResults(r.results, "val-summary",
      `<div class="stat-row"><div class="stat"><div class="n" style="color:var(--high)">${r.summary.flagged}</div><div class="l">মেয়াদ/entitlement ব্যত্যয়</div></div></div>`);
  };
  $("run-ev").onclick = async () => {
    const text = $("ev-text").value;
    if (!text.trim()) return;
    const r = await api.send("POST", "/api/checks/evidence/scan", {
      documents: [{ id: "paste", filename: "paste.txt", ocrStatus: "done", ocrText: text }] });
    const chips = (r.groups[0] && r.groups[0].chips) || [];
    $("ev-out").innerHTML = chips.length ? `<div class="tablewrap"><table><thead><tr>
      <th class="num">মান</th><th>পৃ.</th><th>উৎস টেক্সট</th><th>সাজেশন (check → field)</th><th class="num">confidence</th></tr></thead>
      <tbody>${chips.map((c) => `<tr><td class="num">${bdt(c.value)}</td><td>${c.page}</td>
        <td style="white-space:normal">${esc(c.sourceText)}</td>
        <td>${c.suggestions.length ? esc(c.suggestions[0].checkTitle) + " → " + esc(c.suggestions[0].inputLabel) : "—"}</td>
        <td class="num">${Math.round(c.confidence * 100)}%</td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty">কোনো সংখ্যা পাওয়া যায়নি।</div>`;
  };
}

// scalar fields only, first ~9
function autoCols(obj) {
  return Object.keys(obj)
    .filter((k) => { const v = obj[k]; return v === null || ["string", "number", "boolean"].includes(typeof v); })
    .slice(0, 9)
    .map((k) => [k, k, typeof obj[k] === "number" ? 1 : 0]);
}
