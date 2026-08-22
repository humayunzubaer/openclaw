// সংখ্যাগত auto-check ইঞ্জিন — বন্ড অডিটের মূল reconciliation।
//
// মডিউলে থাকে শুধু ইনপুটের ডিক্লারেটিভ স্পেক (serializable → frontend-এ যায়)।
// প্রকৃত হিসাব এখানে, check id দিয়ে keyed। এভাবে ফর্মুলা একটাই জায়গায়, testable,
// আর মডিউল অবজেক্ট JSON-safe থাকে।
//
// প্রতিটি compute ফাংশন parsed values (Number, না দিলে NaN) নেয়, একটি result দেয়:
//   { status, severity, discrepancy, unit, revenueImplication, observation, breakdown }
// status: "ok" (ব্যত্যয় নেই) | "flag" (অসঙ্গতি) | "insufficient" (তথ্য অসম্পূর্ণ)

const round2 = (n) => Math.round((Number(n) + Number.EPSILON) * 100) / 100;
const bdt = (n) => Number(n || 0).toLocaleString("en-BD");
const q = (n) => round2(n).toLocaleString("en-BD"); // পরিমাণ ফরম্যাট

/** required key গুলোর কোনোটি NaN হলে insufficient; সব ইনপুট খালি হলেও insufficient */
function guard(values, spec) {
  const keys = spec.inputs.map((i) => i.key);
  const anyEntered = keys.some((k) => Number.isFinite(values[k]));
  if (!anyEntered) return { status: "insufficient", reason: "কোনো সংখ্যা দেওয়া হয়নি" };
  const missing = spec.inputs
    .filter((i) => !i.optional && !Number.isFinite(values[i.key]))
    .map((i) => i.label);
  if (missing.length) return { status: "insufficient", reason: `প্রয়োজনীয় তথ্য অনুপস্থিত: ${missing.join(", ")}` };
  return null;
}

const ok = (severity, observation, extra = {}) => ({ status: "ok", severity: severity ?? "low", observation, revenueImplication: 0, ...extra });
const flag = (severity, discrepancy, unit, revenueImplication, observation, breakdown) => ({
  status: "flag", severity, discrepancy: round2(discrepancy), unit,
  revenueImplication: round2(revenueImplication), observation, breakdown,
});

// duty ইনপুট optional; না দিলে 0 ধরে শুধু পরিমাণ-ব্যত্যয় দেখায়।
const duty = (v, key) => (Number.isFinite(v[key]) ? v[key] : 0);

// ---------------- per-check computers ----------------

const COMPUTERS = {
  // ১) আমদানি vs অনুমোদিত entitlement/UP
  "num-entitlement"(v) {
    const excess = v.imported - v.approvedEntitlement;
    if (excess <= 0)
      return ok("low", `আমদানি ${q(v.imported)} একক অনুমোদিত entitlement ${q(v.approvedEntitlement)} একক-এর মধ্যে; entitlement breach নেই।`);
    const rev = excess * duty(v, "dutyPerUnit");
    return flag("high", excess, "একক", rev,
      `অনুমোদিত annual entitlement/UP ${q(v.approvedEntitlement)} একক-এর বিপরীতে আমদানি ${q(v.imported)} একক — অতিরিক্ত ${q(excess)} একক (entitlement breach)। সম্ভাব্য রাজস্ব প্রভাব BDT ${bdt(rev)}।`,
      [{ label: "অনুমোদিত entitlement", value: q(v.approvedEntitlement) }, { label: "আমদানি", value: q(v.imported) }, { label: "অতিরিক্ত", value: q(excess) }]);
  },

  // ২ক) Bill of Entry (আমদানি) vs বন্ড রেজিস্টার লিপিবদ্ধ পরিমাণ
  "num-be-register"(v) {
    const diff = v.beQty - v.registerQty;
    const bd = [
      { label: "B/E আমদানি", value: q(v.beQty) },
      { label: "রেজিস্টারে লিপিবদ্ধ", value: q(v.registerQty) },
      { label: "পার্থক্য", value: q(diff) },
    ];
    if (Math.abs(diff) < 1e-6)
      return ok("low", `B/E ${q(v.beQty)} একক = রেজিস্টারে লিপিবদ্ধ ${q(v.registerQty)} একক; মিল আছে।`, { breakdown: bd });
    if (diff > 0) {
      const rev = diff * duty(v, "dutyPerUnit");
      return flag("high", diff, "একক", rev,
        `Bill of Entry অনুযায়ী আমদানি ${q(v.beQty)} একক, কিন্তু বন্ড রেজিস্টারে লিপিবদ্ধ ${q(v.registerQty)} একক — ${q(diff)} একক রেজিস্টারভুক্ত হয়নি (unrecorded raw material; সম্ভাব্য অপসারণ)। সম্ভাব্য রাজস্ব প্রভাব BDT ${bdt(rev)}।`,
        bd);
    }
    return { ...flag("medium", -diff, "একক", 0,
      `বন্ড রেজিস্টারে লিপিবদ্ধ ${q(v.registerQty)} একক B/E আমদানি ${q(v.beQty)} একক-এর চেয়ে ${q(-diff)} একক বেশি — over-recording/রেকর্ড অসঙ্গতি; যাচাই করুন। স্বয়ংক্রিয় রাজস্ব ধরা হয়নি।`,
      bd) };
  },

  // ২) প্রকৃত ব্যবহার vs অনুমোদিত input-output coefficient
  "num-coefficient"(v) {
    const allowed = v.finishedProduced * v.coeffPerUnit;
    const excess = v.actualConsumed - allowed;
    if (excess <= 0)
      return ok("low", `উৎপাদন ${q(v.finishedProduced)} × coefficient ${q(v.coeffPerUnit)} = অনুমোদিত ব্যবহার ${q(allowed)} একক; প্রকৃত ব্যবহার ${q(v.actualConsumed)} একক — coefficient-এর মধ্যে।`);
    const rev = excess * duty(v, "dutyPerRawUnit");
    return flag("high", excess, "একক", rev,
      `উৎপাদন ${q(v.finishedProduced)} একক × অনুমোদিত coefficient ${q(v.coeffPerUnit)} = অনুমোদিত কাঁচামাল ${q(allowed)} একক; প্রকৃত ব্যবহার ${q(v.actualConsumed)} একক — অতিরিক্ত ${q(excess)} একক। সম্ভাব্য রাজস্ব প্রভাব BDT ${bdt(rev)}।`,
      [{ label: "অনুমোদিত ব্যবহার", value: q(allowed) }, { label: "প্রকৃত ব্যবহার", value: q(v.actualConsumed) }, { label: "অতিরিক্ত", value: q(excess) }]);
  },

  // ২খ) UD-তে দাবিকৃত ব্যবহার vs প্রকৃত রপ্তানি দিয়ে সমর্থিত ব্যবহার
  "num-ud-export"(v) {
    const unsupported = v.udClaimedRaw - v.exportBackedRaw;
    if (unsupported <= 0)
      return ok("low", `UD-তে দাবিকৃত ব্যবহার ${q(v.udClaimedRaw)} একক প্রকৃত রপ্তানি-সমর্থিত ${q(v.exportBackedRaw)} একক দিয়ে সমর্থিত; ব্যত্যয় নেই।`);
    const rev = unsupported * duty(v, "dutyPerRawUnit");
    return flag("high", unsupported, "একক", rev,
      `UD-তে দাবিকৃত কাঁচামাল ব্যবহার ${q(v.udClaimedRaw)} একক, কিন্তু প্রকৃত রপ্তানি (Bill of Export) দিয়ে সমর্থিত মাত্র ${q(v.exportBackedRaw)} একক — অসমর্থিত ${q(unsupported)} একক (রপ্তানি ছাড়াই শুল্কমুক্ত কাঁচামাল ব্যবহার)। সম্ভাব্য রাজস্ব প্রভাব BDT ${bdt(rev)}।`,
      [{ label: "UD দাবি", value: q(v.udClaimedRaw) }, { label: "রপ্তানি-সমর্থিত", value: q(v.exportBackedRaw) }, { label: "অসমর্থিত", value: q(unsupported) }]);
  },

  // ৩) কাঁচামাল material balance — অহিসাবকৃত (সম্ভাব্য স্থানীয় অপসারণ)
  "num-material-balance"(v) {
    const wastage = Number.isFinite(v.wastageAllowedQty) ? v.wastageAllowedQty : 0;
    const available = v.openingStock + v.imported;
    const accounted = v.consumedForExport + wastage + v.closingStock;
    const unaccounted = available - accounted;
    const bd = [
      { label: "প্রাপ্যতা (Opening+Import)", value: q(available) },
      { label: "হিসাবভুক্ত (Export ব্যবহার+অপচয়+Closing)", value: q(accounted) },
      { label: "পার্থক্য", value: q(unaccounted) },
    ];
    if (Math.abs(unaccounted) < 1e-6)
      return ok("low", `কাঁচামাল ব্যালেন্স সঠিক: প্রাপ্যতা ${q(available)} = হিসাবভুক্ত ${q(accounted)} একক; ঘাটতি/উদ্বৃত্ত নেই।`, { breakdown: bd });
    if (unaccounted > 0) {
      const rev = unaccounted * duty(v, "dutyPerRawUnit");
      return flag("high", unaccounted, "একক", rev,
        `Opening ${q(v.openingStock)} + Import ${q(v.imported)} = ${q(available)} একক; হিসাবভুক্ত (রপ্তানি-ব্যবহার ${q(v.consumedForExport)} + অপচয় ${q(wastage)} + Closing ${q(v.closingStock)}) = ${q(accounted)} একক; অহিসাবকৃত ঘাটতি ${q(unaccounted)} একক — সম্ভাব্য শুল্কমুক্ত কাঁচামালের স্থানীয় অপসারণ/বিক্রয়। সম্ভাব্য রাজস্ব প্রভাব BDT ${bdt(rev)}।`,
        bd);
    }
    return { ...flag("medium", -unaccounted, "একক", 0,
      `হিসাবভুক্ত পরিমাণ প্রাপ্যতার চেয়ে ${q(-unaccounted)} একক বেশি — রেকর্ডে অসঙ্গতি (over-accounting)। রেজিস্টার যাচাই করুন; স্বয়ংক্রিয় রাজস্ব ধরা হয়নি।`,
      bd) };
  },

  // ৪) দাবিকৃত অপচয় vs অনুমোদিত অপচয় হার
  "num-wastage"(v) {
    const allowedQty = v.consumedRaw * (v.allowedWastagePct / 100);
    const excess = v.declaredWastageQty - allowedQty;
    if (excess <= 0)
      return ok("low", `অনুমোদিত অপচয় ${q(v.allowedWastagePct)}% × ব্যবহৃত ${q(v.consumedRaw)} = ${q(allowedQty)} একক; দাবিকৃত অপচয় ${q(v.declaredWastageQty)} একক — হারের মধ্যে।`);
    const rev = excess * duty(v, "dutyPerRawUnit");
    return flag("high", excess, "একক", rev,
      `অনুমোদিত অপচয় হার ${q(v.allowedWastagePct)}% × ব্যবহৃত কাঁচামাল ${q(v.consumedRaw)} = অনুমোদিত অপচয় ${q(allowedQty)} একক; দাবিকৃত অপচয় ${q(v.declaredWastageQty)} একক — অতিরিক্ত ${q(excess)} একক (over-wastage)। সম্ভাব্য রাজস্ব প্রভাব BDT ${bdt(rev)}।`,
      [{ label: "অনুমোদিত অপচয়", value: q(allowedQty) }, { label: "দাবিকৃত অপচয়", value: q(v.declaredWastageQty) }, { label: "অতিরিক্ত", value: q(excess) }]);
  },

  // ৫) মেয়াদোত্তীর্ণ (২ বছরের বেশি) বন্ডে থাকা কাঁচামাল — শুল্ক পরিশোধযোগ্য
  "num-overstay"(v) {
    if (v.overstayQty <= 0)
      return ok("low", "মেয়াদোত্তীর্ণ (২ বছরের বেশি) বন্ডে থাকা কাঁচামাল নেই।");
    const rev = v.overstayQty * duty(v, "dutyPerRawUnit");
    return flag("medium", v.overstayQty, "একক", rev,
      `নির্ধারিত মেয়াদ (সাধারণত ২ বছর) অতিক্রান্ত বন্ডে থাকা কাঁচামাল ${q(v.overstayQty)} একক — শুল্ক-কর পরিশোধযোগ্য হয়ে পড়ে। সম্ভাব্য রাজস্ব প্রভাব BDT ${bdt(rev)}।`,
      [{ label: "মেয়াদোত্তীর্ণ পরিমাণ", value: q(v.overstayQty) }]);
  },
};

/** একটি check-এর জন্য ইনপুট map → parsed Number map (খালি → NaN) */
function parseValues(spec, raw) {
  const out = {};
  for (const inp of spec.inputs) {
    const val = raw?.[inp.key];
    out[inp.key] = val === "" || val === null || val === undefined ? NaN : Number(val);
  }
  return out;
}

/**
 * মডিউলের numericChecks স্পেক + auditor-এর ইনপুট থেকে সব check চালায়।
 * @returns {{ results: Array, summary: { flagged:number, totalRevenue:number } }}
 */
export function runNumericChecks(module, inputsByCheck = {}) {
  const specs = module?.numericChecks ?? [];
  const results = specs.map((spec) => {
    const base = { id: spec.id, title: spec.title, area: spec.area, legalRef: spec.legalRef ?? null };
    const compute = COMPUTERS[spec.id];
    if (!compute) return { ...base, status: "insufficient", severity: "low", observation: "এই check-এর হিসাব এখনো যুক্ত হয়নি।", revenueImplication: 0 };
    const values = parseValues(spec, inputsByCheck[spec.id]);
    const g = guard(values, spec);
    if (g) return { ...base, severity: "low", revenueImplication: 0, observation: g.reason, ...g };
    return { ...base, ...compute(values) };
  });
  const flagged = results.filter((r) => r.status === "flag");
  const totalRevenue = flagged.reduce((s, r) => s + Number(r.revenueImplication || 0), 0);
  return { results, summary: { flagged: flagged.length, totalRevenue: round2(totalRevenue) } };
}

/** flag হওয়া একটি numeric result → finding payload (storage.addFinding-এর শেপে) */
export function resultToFinding(result) {
  return {
    checklistId: null,
    area: result.area,
    title: result.title,
    observation: result.observation,
    legalRef: result.legalRef ?? null,
    revenueImplication: Number(result.revenueImplication || 0),
    severity: result.severity ?? "medium",
    source: "numeric",
  };
}
