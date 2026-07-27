// AI বিশ্লেষণ স্তর — pluggable provider।
//   - "none"   → নিয়ম-ভিত্তিক খসড়া (AI ছাড়া, ১০০% অফলাইন)
//   - "ollama" → লোকাল মডেল (ডেটা কম্পিউটার ছাড়ে না; Ollama চালু থাকা লাগে)
//   - "claude" → Claude API (নির্ভুল; OCR টেক্সট API-তে যায়; API key লাগে)
//
// প্রতিটি provider একই ইন্টারফেস দেয়: draftFindings({ module, documents, settings }).
// ollama/claude মডেলের কাছ থেকে JSON চায় ও পার্স করে; ব্যর্থ হলে বোধগম্য error।

const CHECKLIST_DOC_HINTS = {
  "lic-validity": ["bond-license"],
  "ent-limit": ["entitlement", "bill-of-entry"],
  "be-vs-register": ["bill-of-entry", "bond-register-raw"],
  "coefficient-check": ["io-coefficient", "bond-register-raw"],
  "ud-vs-export": ["utilization-declaration", "bill-of-export"],
  "unused-stock": ["stock-report", "bond-register-raw"],
  overstay: ["bond-register-raw", "stock-report"],
  wastage: ["io-coefficient", "stock-report"],
  "revenue-loss": [],
};

function missingDocsFor(module, checklistId, presentCategories) {
  const wanted = CHECKLIST_DOC_HINTS[checklistId] ?? [];
  const labelOf = (catId) => module.documentTypes.find((d) => d.id === catId)?.label ?? catId;
  return wanted.filter((cat) => !presentCategories.has(cat)).map(labelOf);
}

// ---------- rule-based (offline) ----------
function ruleBasedDrafts(module, documents) {
  const present = new Set(documents.map((d) => d.category));
  return module.checklist.map((c) => {
    const missing = missingDocsFor(module, c.id, present);
    const note = missing.length
      ? `সংশ্লিষ্ট নথি অনুপস্থিত: ${missing.join(", ")} — সংগ্রহ করে যাচাই করুন।`
      : "নথি উপস্থিত — মান যাচাই করে অসঙ্গতি লিপিবদ্ধ করুন।";
    return {
      checklistId: c.id,
      area: c.area,
      title: c.question,
      observation: `[খসড়া] ${note}`,
      legalRef: c.legalRef ?? null,
      severity: "medium",
      revenueImplication: 0,
    };
  });
}

// ---------- shared prompt for LLM providers ----------
function buildPrompt(module, documents) {
  const docBlocks = documents
    .filter((d) => d.ocrText?.trim())
    .map((d) => `### নথি: ${d.filename} (category: ${d.category})\n${d.ocrText.slice(0, 6000)}`)
    .join("\n\n");
  const checklist = module.checklist.map((c) => `- (${c.id}) [${c.area}] ${c.question}`).join("\n");

  return `তুমি একজন বাংলাদেশ কাস্টমস বন্ড অডিট বিশেষজ্ঞ। নিচের checklist ও নথির OCR টেক্সট বিশ্লেষণ করে সম্ভাব্য অসঙ্গতি (findings) বের করো।
রিপোর্ট বাংলায়, technical term ইংরেজিতে (Bill of Entry, Coefficient, Rebate ইত্যাদি)।

# মডিউল: ${module.title}

# Checklist:
${checklist}

# নথিসমূহ (OCR):
${docBlocks || "(কোনো OCR টেক্সট নেই — শুধু checklist ও নথির উপস্থিতি অনুযায়ী মূল্যায়ন করো)"}

শুধুমাত্র একটি JSON array ফেরত দাও, অন্য কোনো লেখা নয়। প্রতিটি item:
{"checklistId": string|null, "area": string, "title": string, "observation": string, "legalRef": string|null, "severity": "low"|"medium"|"high", "revenueImplication": number}
legalRef হতে হবে এই কীগুলোর একটি বা null: customs-act-13, customs-act-21, customs-act-156, bwl-rules.`;
}

function parseDrafts(text) {
  const start = text.indexOf("[");
  const end = text.lastIndexOf("]");
  if (start === -1 || end === -1) throw new Error("মডেল থেকে JSON array পাওয়া যায়নি।");
  const arr = JSON.parse(text.slice(start, end + 1));
  return arr.map((d) => ({
    checklistId: d.checklistId ?? null,
    area: String(d.area ?? ""),
    title: String(d.title ?? ""),
    observation: String(d.observation ?? ""),
    legalRef: d.legalRef ?? null,
    severity: ["low", "medium", "high"].includes(d.severity) ? d.severity : "medium",
    revenueImplication: Number(d.revenueImplication) || 0,
  }));
}

// ---------- ollama ----------
async function ollamaDrafts(module, documents, settings) {
  const { baseUrl, model } = settings.ollama;
  let res;
  try {
    res = await fetch(`${baseUrl.replace(/\/$/, "")}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, prompt: buildPrompt(module, documents), stream: false }),
    });
  } catch {
    throw new Error(`Ollama-তে সংযোগ ব্যর্থ (${baseUrl})। Ollama চালু আছে কি? চালান: ollama serve`);
  }
  if (!res.ok) throw new Error(`Ollama error ${res.status}: মডেল "${model}" ইনস্টল আছে কি? (ollama pull ${model})`);
  const data = await res.json();
  return parseDrafts(data.response ?? "");
}

// ---------- claude ----------
async function claudeDrafts(module, documents, settings) {
  const { apiKey, model } = settings.claude;
  if (!apiKey) throw new Error("Claude API key সেট করা নেই। Settings-এ যুক্ত করুন।");
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model,
      max_tokens: 4000,
      messages: [{ role: "user", content: buildPrompt(module, documents) }],
    }),
  });
  if (!res.ok) throw new Error(`Claude API error ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  const text = (data.content ?? []).map((b) => b.text ?? "").join("");
  return parseDrafts(text);
}

// ---------- registry ----------
const meta = {
  none: { id: "none", label: "শুধু নিয়ম-ভিত্তিক (AI ছাড়া, সম্পূর্ণ অফলাইন)", offline: true },
  ollama: { id: "ollama", label: "লোকাল মডেল — Ollama (অফলাইন)", offline: true },
  claude: { id: "claude", label: "Claude API (অনলাইন, নির্ভুল)", offline: false },
};

export function listProviders() {
  return Object.values(meta);
}

export async function draftFindings(providerId, { module, documents, settings }) {
  if (providerId === "ollama") return { provider: "ollama", drafts: await ollamaDrafts(module, documents, settings) };
  if (providerId === "claude") return { provider: "claude", drafts: await claudeDrafts(module, documents, settings) };
  return { provider: "none", drafts: ruleBasedDrafts(module, documents) };
}
