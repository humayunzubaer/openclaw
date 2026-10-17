// Smart Evidence Chip extraction — context-aware।
//
// generic number-chip নয়: প্রতিটি extracted value একটি Evidence Chip, যা ধরে রাখে
//   document (docId + filename), page, source text (আশপাশের OCR স্নিপেট),
//   field suggestion (কোন numeric-check ইনপুটে বসতে পারে + কেন), confidence score।
// প্রয়োগ করলে server provenance + audit trail (evidence.json) লিখে রাখে।
//
// নথির ফরম্যাট একেক রকম বলে "auto-map" নয় — টুল সাজেশন দেয়, নিরীক্ষক প্রয়োগ করেন।

const BN_DIGITS = "০১২৩৪৫৬৭৮৯";
const bnToAscii = (s) => s.replace(/[০-৯]/g, (d) => String(BN_DIGITS.indexOf(d)));

const round2 = (n) => Math.round((n + Number.EPSILON) * 100) / 100;
const clamp01 = (n) => Math.max(0, Math.min(1, n));

// numeric token: ASCII/বাংলা অঙ্ক, thousands separator (,) ও দশমিক (.)সহ।
const NUM_RE = /[0-9০-৯][0-9০-৯,]*(?:\.[0-9০-৯]+)?/g;

// per-input synonyms (বাংলা + English) — context থেকে সঠিক field খুঁজতে।
const SYN = {
  approvedEntitlement: ["entitlement", "up", "utilization permission", "অনুমোদিত", "এনটাইটেলমেন্ট", "প্রাপ্যতা"],
  imported: ["import", "imported", "আমদানি", "bill of entry", "b/e", "be"],
  dutyPerUnit: ["duty", "tax", "শুল্ক", "কর", "রাজস্ব", "rate", "হার"],
  finishedProduced: ["finished", "production", "produced", "উৎপাদন", "উৎপাদিত", "পণ্য"],
  coeffPerUnit: ["coefficient", "coeff", "input-output", "গুণাঙ্ক", "হার"],
  actualConsumed: ["consumed", "consumption", "ব্যবহার", "ব্যবহৃত", "খরচ"],
  dutyPerRawUnit: ["duty", "tax", "শুল্ক", "কর", "রাজস্ব", "rate"],
  beQty: ["bill of entry", "b/e", "be", "আমদানি", "imported"],
  registerQty: ["register", "রেজিস্টার", "রেজিস্ট্রার", "recorded", "লিপিবদ্ধ", "ইন-টু-বন্ড", "in-bond"],
  udClaimedRaw: ["ud", "up", "ep", "utilization declaration", "sales contract", "claimed", "দাবি", "দাবিকৃত"],
  exportBackedRaw: ["export", "রপ্তানি", "bill of export", "exported"],
  openingStock: ["opening", "প্রারম্ভিক", "opening stock", "প্রারম্ভিক মজুদ", "মজুদ"],
  consumedForExport: ["consumed", "export", "রপ্তানি", "ব্যবহৃত"],
  wastageAllowedQty: ["wastage", "অপচয়", "waste", "allowed"],
  closingStock: ["closing", "সমাপনী", "closing stock", "সমাপনী মজুদ", "মজুদ"],
  allowedWastagePct: ["wastage", "অপচয়", "percent", "হার", "rate"],
  consumedRaw: ["consumed", "ব্যবহৃত", "consumption", "ব্যবহার"],
  declaredWastageQty: ["wastage", "অপচয়", "declared", "দাবিকৃত"],
  overstayQty: ["overstay", "মেয়াদোত্তীর্ণ", "expired", "overdue", "মেয়াদ"],
};

const UNIT_CUES = ["৳", "bdt", "টাকা", "একক", "kg", "kgs", "mt", "%", "pcs", "pc", "unit", "পিস", "yds", "gm"];
const STOP = new Set(["vs", "এবং", "and", "the", "of", "—", "-", "b/e"]);

function tokens(str) {
  // \p{M} রাখা জরুরি: বাংলা যুক্তবর্ণ/মাত্রা combining mark — না রাখলে শব্দ ভেঙে যায়।
  return String(str || "")
    .toLowerCase()
    .split(/[^\p{L}\p{N}\p{M}/%]+/u)
    .map((t) => t.trim())
    .filter((t) => t.length >= 2 && !STOP.has(t));
}

// দুই-স্তর index: check-level keyword (title+area) কোন CHECK বাছে;
// input-level keyword (SYN + label − title tokens) কোন FIELD বাছে।
// এভাবে "মেশিনারিজ" ঠিক check-এ নেয়, আর "রেজিস্টার/লিপিবদ্ধ" ঠিক field-এ।
function buildKeywordIndex(module) {
  const checks = [];
  for (const check of module.numericChecks ?? []) {
    const titleToks = new Set([...tokens(check.title), ...tokens(check.area)]);
    const checkKeywords = [...titleToks].map((t) => [t, 0.5]);
    const inputs = check.inputs.map((inp) => {
      const kw = new Map();
      for (const s of SYN[inp.key] ?? []) kw.set(s.toLowerCase(), Math.max(kw.get(s.toLowerCase()) ?? 0, 0.35));
      for (const t of tokens(inp.label)) if (!titleToks.has(t)) kw.set(t, Math.max(kw.get(t) ?? 0, 0.3));
      return { inputKey: inp.key, inputLabel: inp.label, keywords: [...kw.entries()] };
    });
    checks.push({ checkId: check.id, checkTitle: check.title, checkKeywords, inputs });
  }
  return checks;
}

/** context (lowercase) → ranked field suggestions */
function suggestFields(contextLower, keywordIndex) {
  const scored = [];
  for (const check of keywordIndex) {
    let checkScore = 0;
    for (const [kw, w] of check.checkKeywords) if (contextLower.includes(kw)) checkScore += w;
    for (const inp of check.inputs) {
      let inputScore = 0;
      for (const [kw, w] of inp.keywords) if (contextLower.includes(kw)) inputScore += w;
      if (inputScore <= 0.15) continue;              // field না মিললে suggest করি না
      const combined = inputScore + 0.4 * checkScore; // check-match শুধু tie-break/booster
      scored.push({ checkId: check.checkId, checkTitle: check.checkTitle, inputKey: inp.inputKey, inputLabel: inp.inputLabel, combined, score: round2(clamp01(combined)) });
    }
  }
  scored.sort((a, b) => b.combined - a.combined);
  return scored.slice(0, 3).map(({ combined, ...s }) => s);
}

function tokenQuality(raw) {
  const digits = raw.replace(/[^0-9০-৯]/g, "").length;
  if (raw.includes(".") || raw.includes(",")) return 0.9;
  if (digits >= 2) return 0.7;
  return 0.4;
}

/** এক পৃষ্ঠার OCR টেক্সট → Evidence Chip[] */
function extractFromText(text, page, keywordIndex, ctx) {
  const chips = [];
  const src = String(text || "");
  for (const m of src.matchAll(NUM_RE)) {
    const raw = m[0];
    const normalized = bnToAscii(raw).replace(/,/g, "");
    if ((normalized.match(/\./g) || []).length > 1) continue;
    const value = Number.parseFloat(normalized);
    if (!Number.isFinite(value)) continue;

    const start = Math.max(0, m.index - 45);
    const end = Math.min(src.length, m.index + raw.length + 45);
    const sourceText = src.slice(start, end).replace(/\s+/g, " ").trim();
    const lower = sourceText.toLowerCase();

    const suggestions = suggestFields(lower, keywordIndex);
    const fieldScore = suggestions.length ? suggestions[0].score : 0;
    const unitCue = UNIT_CUES.some((u) => lower.includes(u)) ? 0.15 : 0;
    const confidence = round2(clamp01(0.45 * tokenQuality(raw) + 0.45 * fieldScore + unitCue));

    chips.push({
      id: `chip_${ctx.docId}_${page}_${m.index}`,
      docId: ctx.docId,
      docFilename: ctx.docFilename,
      page,
      value: round2(value),
      raw,
      offset: m.index,
      sourceText,
      suggestions,
      confidence,
    });
  }
  return chips;
}

/** একটি নথি (ocrText সহ) → { docId, filename, chips } */
export function extractDocument(doc, module, { maxChips = 250 } = {}) {
  const keywordIndex = buildKeywordIndex(module);
  const pages = String(doc.ocrText || "").split("\f");
  const chips = [];
  pages.forEach((pageText, i) => {
    for (const c of extractFromText(pageText, i + 1, keywordIndex, { docId: doc.id, docFilename: doc.filename })) {
      chips.push(c);
      if (chips.length >= maxChips) return;
    }
  });
  // confidence-এর নিচে নামা ক্রমে সাজাই — উপরে সবচেয়ে ভরসাযোগ্য।
  chips.sort((a, b) => b.confidence - a.confidence || a.offset - b.offset);
  return { docId: doc.id, filename: doc.filename, chips };
}

/** সব OCR-করা নথি স্ক্যান করে group করে ফেরত দেয় */
export function scanDocuments(documents, module) {
  const groups = [];
  for (const doc of documents) {
    if (doc.ocrStatus !== "done" || !doc.ocrText?.trim()) continue;
    const g = extractDocument(doc, module);
    if (g.chips.length) groups.push(g);
  }
  const totalChips = groups.reduce((s, g) => s + g.chips.length, 0);
  return { groups, totalChips, scannedDocs: groups.length };
}
