// Import Intelligence — frontend (vanilla JS, no build)

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const money = (n) => "৳ " + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const num = (n) => Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 3 });

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

// scalar fields only, first ~9
function autoCols(obj) {
  return Object.keys(obj)
    .filter((k) => { const v = obj[k]; return v === null || ["string", "number", "boolean"].includes(typeof v); })
    .slice(0, 9)
    .map((k) => [k, k, typeof obj[k] === "number" ? 1 : 0]);
}
