// আইনভিত্তিক নলেজ বেস — বন্ড অডিট
//
// প্রতিটি finding-এর সাথে প্রাসঙ্গিক আইন/বিধি রেফারেন্স যুক্ত করার জন্য।
// এগুলো editable ডিফল্ট — বর্তমান সংশোধিত SRO/বিধি অনুযায়ী auditor হালনাগাদ করবেন।
// (RAG/AI যুক্ত হলে এই টেবিলই retrieval-এর উৎস হবে।)

/** @typedef {{ id: string, title: string, summary: string, citation: string }} LegalRef */

export const bondLegalRefs = /** @type {Record<string, LegalRef>} */ ({
  "customs-act-13": {
    id: "customs-act-13",
    title: "Customs Act, 1969 — Warehousing (Bonded Warehouse)",
    summary: "বন্ডেড ওয়্যারহাউস লাইসেন্সিং ও শুল্কমুক্ত আমদানির শর্তাবলি।",
    citation: "The Customs Act, 1969, Ch. XI (Warehousing)",
  },
  "customs-act-21": {
    id: "customs-act-21",
    title: "Customs Act, 1969 — Drawback / Utilization",
    summary: "শুল্কমুক্ত আমদানিকৃত পণ্যের রপ্তানিমুখী ব্যবহারের শর্ত ও সমন্বয়।",
    citation: "The Customs Act, 1969 (Utilization / Drawback provisions)",
  },
  "customs-act-156": {
    id: "customs-act-156",
    title: "Customs Act, 1969 — Section 156 (Penalty / Recovery)",
    summary: "শর্ত লঙ্ঘন, ঘাটতি বা অপব্যবহারে শুল্ক-কর আদায় ও জরিমানা।",
    citation: "The Customs Act, 1969, Section 156",
  },
  "bwl-rules": {
    id: "bwl-rules",
    title: "Bonded Warehouse Licensing Rules",
    summary: "লাইসেন্স, entitlement, UP/UD, input-output coefficient, রেজিস্টার সংরক্ষণ, মেয়াদ ও অপচয় হারের বিধান।",
    citation: "Bonded Warehouse Licensing Rules (current SRO — verify latest amendment)",
  },
});

/** finding-এর legalRef কী থেকে reference object ফেরত দেয় */
export function resolveLegalRef(key) {
  return bondLegalRefs[key] ?? null;
}
