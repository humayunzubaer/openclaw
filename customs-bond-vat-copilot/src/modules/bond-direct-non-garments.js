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

  // সংখ্যাগত auto-check: auditor সংখ্যা বসাবেন, ইঞ্জিন (src/checks/numeric.js)
  // ঘাটতি ও রাজস্ব হিসাব করবে। এখানে শুধু serializable ইনপুট-স্পেক (compute নয়)।
  // inputs[].optional === true মানে না দিলে 0 ধরা হয় (সাধারণত duty/rate ফিল্ড)।
  numericChecks: [
    {
      id: "num-entitlement",
      title: "Entitlement অতিক্রম (আমদানি vs অনুমোদিত)",
      area: "লাইসেন্স ও Entitlement",
      legalRef: "bwl-rules",
      formula: "অতিরিক্ত = আমদানি − অনুমোদিত entitlement; রাজস্ব = অতিরিক্ত × শুল্ক-কর/একক",
      inputs: [
        { key: "approvedEntitlement", label: "অনুমোদিত annual entitlement / UP", unit: "একক" },
        { key: "imported", label: "প্রকৃত আমদানি", unit: "একক" },
        { key: "dutyPerUnit", label: "শুল্ক-কর / একক", unit: "BDT", optional: true },
      ],
    },
    {
      id: "num-be-register",
      title: "Bill of Entry vs বন্ড রেজিস্টার (রেকর্ড মিল)",
      area: "আমদানি বনাম রেকর্ড",
      legalRef: "bwl-rules",
      formula: "পার্থক্য = B/E আমদানি − রেজিস্টারে লিপিবদ্ধ; কম রেকর্ড × শুল্ক-কর/একক = রাজস্ব",
      inputs: [
        { key: "beQty", label: "Bill of Entry অনুযায়ী আমদানি", unit: "একক" },
        { key: "registerQty", label: "বন্ড রেজিস্টারে লিপিবদ্ধ", unit: "একক" },
        { key: "dutyPerUnit", label: "শুল্ক-কর / একক", unit: "BDT", optional: true },
      ],
    },
    {
      id: "num-coefficient",
      title: "Coefficient অনুযায়ী অতিরিক্ত ব্যবহার",
      area: "ব্যবহার (Consumption)",
      legalRef: "bwl-rules",
      formula: "অনুমোদিত = উৎপাদন × coefficient; অতিরিক্ত = প্রকৃত ব্যবহার − অনুমোদিত; রাজস্ব = অতিরিক্ত × শুল্ক-কর/একক",
      inputs: [
        { key: "finishedProduced", label: "উৎপাদিত পণ্য (Finished)", unit: "একক" },
        { key: "coeffPerUnit", label: "অনুমোদিত coefficient (কাঁচামাল/একক পণ্য)", unit: "" },
        { key: "actualConsumed", label: "প্রকৃত কাঁচামাল ব্যবহার", unit: "একক" },
        { key: "dutyPerRawUnit", label: "শুল্ক-কর / একক কাঁচামাল", unit: "BDT", optional: true },
      ],
    },
    {
      id: "num-ud-export",
      title: "UD দাবি vs প্রকৃত রপ্তানি (সমন্বয়)",
      area: "রপ্তানি সমন্বয়",
      legalRef: "customs-act-21",
      formula: "অসমর্থিত = UD দাবিকৃত ব্যবহার − রপ্তানি-সমর্থিত ব্যবহার; অসমর্থিত × শুল্ক-কর/একক = রাজস্ব",
      inputs: [
        { key: "udClaimedRaw", label: "UD-তে দাবিকৃত কাঁচামাল ব্যবহার", unit: "একক" },
        { key: "exportBackedRaw", label: "প্রকৃত রপ্তানি-সমর্থিত ব্যবহার", unit: "একক" },
        { key: "dutyPerRawUnit", label: "শুল্ক-কর / একক কাঁচামাল", unit: "BDT", optional: true },
      ],
    },
    {
      id: "num-material-balance",
      title: "কাঁচামাল Reconciliation (অহিসাবকৃত)",
      area: "স্টক ও উদ্বৃত্ত",
      legalRef: "customs-act-156",
      formula: "অহিসাবকৃত = (Opening+Import) − (রপ্তানি-ব্যবহার + অপচয় + Closing); ঘাটতি × শুল্ক-কর/একক = রাজস্ব",
      inputs: [
        { key: "openingStock", label: "প্রারম্ভিক মজুদ (Opening)", unit: "একক" },
        { key: "imported", label: "আমদানি (Import)", unit: "একক" },
        { key: "consumedForExport", label: "রপ্তানিতে ব্যবহৃত কাঁচামাল", unit: "একক" },
        { key: "wastageAllowedQty", label: "স্বীকৃত অপচয় পরিমাণ", unit: "একক", optional: true },
        { key: "closingStock", label: "সমাপনী মজুদ (Closing)", unit: "একক" },
        { key: "dutyPerRawUnit", label: "শুল্ক-কর / একক কাঁচামাল", unit: "BDT", optional: true },
      ],
    },
    {
      id: "num-wastage",
      title: "অপচয় (Wastage) অনুমোদিত হারের বেশি",
      area: "অপচয় (Wastage)",
      legalRef: "bwl-rules",
      formula: "অনুমোদিত অপচয় = ব্যবহৃত × হার%; অতিরিক্ত = দাবিকৃত − অনুমোদিত; রাজস্ব = অতিরিক্ত × শুল্ক-কর/একক",
      inputs: [
        { key: "consumedRaw", label: "ব্যবহৃত কাঁচামাল", unit: "একক" },
        { key: "allowedWastagePct", label: "অনুমোদিত অপচয় হার", unit: "%" },
        { key: "declaredWastageQty", label: "দাবিকৃত অপচয়", unit: "একক" },
        { key: "dutyPerRawUnit", label: "শুল্ক-কর / একক কাঁচামাল", unit: "BDT", optional: true },
      ],
    },
    {
      id: "num-overstay",
      title: "মেয়াদোত্তীর্ণ কাঁচামাল (Overstay)",
      area: "স্টক ও উদ্বৃত্ত",
      legalRef: "bwl-rules",
      formula: "রাজস্ব = মেয়াদোত্তীর্ণ পরিমাণ × শুল্ক-কর/একক (২ বছরের বেশি বন্ডে থাকা কাঁচামাল)",
      inputs: [
        { key: "overstayQty", label: "মেয়াদোত্তীর্ণ (>২ বছর) পরিমাণ", unit: "একক" },
        { key: "dutyPerRawUnit", label: "শুল্ক-কর / একক কাঁচামাল", unit: "BDT", optional: true },
      ],
    },
  ],

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
