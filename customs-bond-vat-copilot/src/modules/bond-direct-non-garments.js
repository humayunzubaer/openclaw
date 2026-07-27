// Audit module: বন্ড অডিট — সরাসরি (পোশাক শিল্প ব্যতীত)
// Direct bonded exporter, non-garments.
//
// এই ফাইলটাই মডিউলের "মস্তিষ্ক": কোন নথি লাগবে, কী কী যাচাই করতে হবে,
// কোন আইন প্রযোজ্য, এবং working paper কী কী সেকশনে ভাগ হবে।
// প্রতিটি নতুন অডিট এই টেমপ্লেট থেকে শুরু হয় — এটাই সময় বাঁচায়।
//
// NOTE: legalRef মানগুলো editable ডিফল্ট। প্রতিটি অডিটে auditor বর্তমান
// SRO/বিধি যাচাই করে নেবেন — উদ্দেশ্য দ্রুত খসড়া দেওয়া, চূড়ান্ত রায় নয়।

/** @typedef {{ id: string, label: string, required: boolean, hint?: string }} DocumentType */
/** @typedef {{ id: string, area: string, question: string, legalRef?: string }} ChecklistItem */

export const bondDirectNonGarments = {
  id: "bond-direct-non-garments",
  category: "bond",
  title: "বন্ড অডিট — সরাসরি (পোশাক শিল্প ব্যতীত)",
  shortTitle: "Direct Bond (Non-Garments)",

  // যে নথিগুলো এই ধরনের অডিটে সংগ্রহ করতে হয়
  documentTypes: /** @type {DocumentType[]} */ ([
    { id: "bond-license", label: "বন্ড লাইসেন্স (Bonded Warehouse Licence)", required: true, hint: "মেয়াদ, entitlement, HS codes যাচাই" },
    { id: "entitlement", label: "Annual Entitlement / Utilization Permission (UP)", required: true },
    { id: "bill-of-entry", label: "Bill of Entry (আমদানি — B/E)", required: true, hint: "কাঁচামাল আমদানির মূল দলিল" },
    { id: "bond-register-raw", label: "বন্ড রেজিস্টার — কাঁচামাল (Raw Materials)", required: true },
    { id: "bond-register-finished", label: "বন্ড রেজিস্টার — উৎপাদিত পণ্য (Finished Goods)", required: true },
    { id: "io-coefficient", label: "Input-Output Coefficient (অনুমোদিত)", required: true, hint: "প্রতি একক পণ্যে অনুমোদিত কাঁচামাল" },
    { id: "utilization-declaration", label: "Utilization Declaration (UD)", required: true },
    { id: "bill-of-export", label: "Bill of Export / রপ্তানি দলিল", required: true },
    { id: "export-lc", label: "Export L/C / Sales Contract", required: false },
    { id: "stock-report", label: "স্টক রিপোর্ট (কাঁচামাল ও উৎপাদিত পণ্য)", required: true },
    { id: "ledger", label: "General Ledger / Purchase-Sales Ledger", required: false },
    { id: "prev-audit", label: "পূর্ববর্তী অডিট রিপোর্ট / আপত্তি", required: false },
  ]),

  // যাচাই-চেকলিস্ট: প্রতিটি item একটি সম্ভাব্য finding-এর উৎস
  checklist: /** @type {ChecklistItem[]} */ ([
    { id: "lic-validity", area: "লাইসেন্স ও Entitlement", question: "বন্ড লাইসেন্স মেয়াদ ও নবায়ন হালনাগাদ আছে কি? আমদানিকৃত HS code entitlement-এর মধ্যে কি?", legalRef: "customs-act-13" },
    { id: "ent-limit", area: "লাইসেন্স ও Entitlement", question: "আমদানির পরিমাণ অনুমোদিত annual entitlement/UP অতিক্রম করেছে কি?", legalRef: "bwl-rules" },
    { id: "be-vs-register", area: "আমদানি বনাম রেকর্ড", question: "প্রতিটি Bill of Entry বন্ড রেজিস্টারে যথাযথভাবে entry হয়েছে কি? পরিমাণ/মূল্য মিল আছে কি?", legalRef: "bwl-rules" },
    { id: "coefficient-check", area: "ব্যবহার (Consumption)", question: "প্রকৃত কাঁচামাল ব্যবহার অনুমোদিত input-output coefficient অনুযায়ী কি? অতিরিক্ত ব্যবহার আছে কি?", legalRef: "bwl-rules" },
    { id: "ud-vs-export", area: "রপ্তানি সমন্বয়", question: "UD-তে দাবিকৃত ব্যবহার প্রকৃত রপ্তানি (Bill of Export) দিয়ে সমর্থিত কি?", legalRef: "customs-act-21" },
    { id: "unused-stock", area: "স্টক ও উদ্বৃত্ত", question: "উদ্বৃত্ত/অব্যবহৃত কাঁচামালের হিসাব মিলছে কি? স্থানীয় বিক্রয়/অপচয়ের প্রমাণ আছে কি?", legalRef: "customs-act-156" },
    { id: "overstay", area: "স্টক ও উদ্বৃত্ত", question: "নির্ধারিত মেয়াদ (সাধারণত ২ বছর) অতিক্রান্ত কাঁচামাল বন্ডে আছে কি?", legalRef: "bwl-rules" },
    { id: "wastage", area: "অপচয় (Wastage)", question: "দাবিকৃত অপচয় অনুমোদিত হার অতিক্রম করেছে কি? অপচয়/স্ক্র্যাপ নিষ্পত্তির রেকর্ড আছে কি?", legalRef: "bwl-rules" },
    { id: "revenue-loss", area: "রাজস্ব প্রভাব", question: "উপরের অসঙ্গতির ফলে ফাঁকি/পরিহারযোগ্য শুল্ক-কর কত? (ঘাটতি × প্রযোজ্য শুল্ক-কর)", legalRef: "customs-act-156" },
  ]),

  // Working Paper-এর সেকশন কাঠামো (রিপোর্টেও এই ক্রম অনুসৃত হয়)
  workingPaperSections: [
    "প্রতিষ্ঠান পরিচিতি ও বন্ড লাইসেন্স তথ্য",
    "আমদানি (Bill of Entry) সমন্বয়",
    "বন্ড রেজিস্টার যাচাই",
    "Input-Output Coefficient বিশ্লেষণ",
    "উৎপাদন ও রপ্তানি (UD vs Export) সমন্বয়",
    "স্টক, উদ্বৃত্ত ও অপচয়",
    "রাজস্ব প্রভাব (Revenue Implication)",
    "সুপারিশ (Recommendations)",
  ],
};
