// মেয়াদ/Entitlement যাচাই ইঞ্জিন — তারিখ ও HS-list ভিত্তিক (সংখ্যাগত নয়)।
//
// numeric.js-এর ধাঁচে: মডিউলে শুধু serializable spec; হিসাব এখানে check id দিয়ে keyed।
// প্রতিটি compute raw input map নেয়, result দেয়:
//   { status: "ok" | "flag" | "insufficient", severity, observation, detail? }
// এগুলো compliance flag — revenue হিসাব নেই (finding-এ revenue 0)।

const DAY = 86400000;

function parseDate(s) {
  if (!s || typeof s !== "string") return null;
  const d = new Date(`${s.trim()}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}
function today() {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}
const fmt = (d) => (d ? d.toISOString().slice(0, 10) : "—");

// HS code / list token: comma/space/newline আলাদা; dot রাখা (5208.11)।
function tokenizeList(s) {
  return [...new Set(String(s || "").toUpperCase().split(/[^0-9A-Z.]+/).map((t) => t.trim()).filter(Boolean))];
}

const ok = (severity, observation) => ({ status: "ok", severity: severity ?? "low", observation });
const flag = (severity, observation, detail) => ({ status: "flag", severity, observation, detail: detail ?? null });
const insufficient = (reason) => ({ status: "insufficient", severity: "low", observation: reason });

const COMPUTERS = {
  // ১) বন্ড লাইসেন্স মেয়াদ vs নিরীক্ষা তারিখ
  "val-license-expiry"(v) {
    const exp = parseDate(v.licenseExpiry);
    if (!exp) return insufficient("লাইসেন্স মেয়াদ শেষের তারিখ দিন (YYYY-MM-DD)।");
    const asOf = parseDate(v.asOf) || today();
    const days = Math.floor((exp - asOf) / DAY);
    if (days < 0)
      return flag("high", `বন্ড লাইসেন্স মেয়াদ ${fmt(exp)} — নিরীক্ষা তারিখ ${fmt(asOf)} অনুযায়ী ${-days} দিন আগে উত্তীর্ণ। নবায়ন ছাড়া বন্ড কার্যক্রম অবৈধ।`, { daysOverdue: -days });
    if (days <= 90)
      return flag("medium", `বন্ড লাইসেন্স মেয়াদ ${fmt(exp)} — আর মাত্র ${days} দিন বাকি; নবায়ন প্রক্রিয়া নিশ্চিত করুন।`, { daysLeft: days });
    return ok("low", `বন্ড লাইসেন্স ${fmt(exp)} পর্যন্ত বৈধ (${days} দিন বাকি)।`);
  },

  // ২) লেনদেন (B/E/রপ্তানি) UP/UD/EP মেয়াদের মধ্যে কি
  "val-up-coverage"(v) {
    const from = parseDate(v.upValidFrom);
    const to = parseDate(v.upValidTo);
    const txn = parseDate(v.transactionDate);
    if (!from || !to || !txn) return insufficient("UP/UD বৈধতার শুরু-শেষ ও লেনদেন তারিখ দিন।");
    if (txn < from || txn > to)
      return flag("high", `লেনদেন তারিখ ${fmt(txn)} UP/UD/EP মেয়াদ (${fmt(from)}–${fmt(to)})-এর বাইরে — এই সময়ে শুল্কমুক্ত সুবিধা প্রযোজ্য নয়।`, { from: fmt(from), to: fmt(to), txn: fmt(txn) });
    return ok("low", `লেনদেন ${fmt(txn)} UP/UD মেয়াদের (${fmt(from)}–${fmt(to)}) মধ্যে।`);
  },

  // ৩) আমদানিকৃত HS code entitlement তালিকায় আছে কি
  "val-hs-entitlement"(v) {
    const ent = tokenizeList(v.entitledHs);
    const imp = tokenizeList(v.importedHs);
    if (!ent.length || !imp.length) return insufficient("অনুমোদিত ও আমদানিকৃত HS code দিন।");
    const entSet = new Set(ent);
    const outside = imp.filter((c) => !entSet.has(c));
    if (outside.length)
      return flag("high", `entitlement-বহির্ভূত HS code আমদানি: ${outside.join(", ")} — লাইসেন্সে অনুমোদিত নয়।`, { outside });
    return ok("low", `সব আমদানিকৃত HS code (${imp.length}টি) entitlement-এর মধ্যে।`);
  },
};

/** মডিউলের validityChecks spec + auditor ইনপুট → সব check চালায় */
export function runValidityChecks(module, inputsByCheck = {}) {
  const specs = module?.validityChecks ?? [];
  const results = specs.map((spec) => {
    const base = { id: spec.id, title: spec.title, area: spec.area, legalRef: spec.legalRef ?? null };
    const compute = COMPUTERS[spec.id];
    if (!compute) return { ...base, status: "insufficient", severity: "low", observation: "এই check-এর হিসাব এখনো যুক্ত হয়নি।" };
    return { ...base, ...compute(inputsByCheck[spec.id] ?? {}) };
  });
  const flagged = results.filter((r) => r.status === "flag");
  return { results, summary: { flagged: flagged.length } };
}

/** flag হওয়া validity result → finding payload (compliance; revenue 0) */
export function validityResultToFinding(result) {
  return {
    checklistId: "lic-validity",
    area: result.area,
    title: result.title,
    observation: result.observation,
    legalRef: result.legalRef ?? null,
    revenueImplication: 0,
    severity: result.severity ?? "medium",
    source: "validity",
  };
}
