// অ্যাপ সেটিংস — লোকাল ফাইলে সংরক্ষিত (settings.json)।
// এখানে AI provider পছন্দ ও তার কনফিগ থাকে। API key কখনো UI-তে ফেরত পাঠানো হয় না।

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FILE = path.join(__dirname, "..", "settings.json");

const DEFAULTS = {
  aiProvider: "none", // none | ollama | claude
  ollama: { baseUrl: "http://localhost:11434", model: "llama3.1" },
  claude: { apiKey: "", model: "claude-sonnet-5" },
};

export async function getSettings() {
  try {
    const raw = JSON.parse(await fs.readFile(FILE, "utf8"));
    return { ...DEFAULTS, ...raw, ollama: { ...DEFAULTS.ollama, ...raw.ollama }, claude: { ...DEFAULTS.claude, ...raw.claude } };
  } catch {
    return { ...DEFAULTS };
  }
}

export async function saveSettings(patch) {
  const cur = await getSettings();
  const next = {
    ...cur,
    ...patch,
    ollama: { ...cur.ollama, ...(patch.ollama ?? {}) },
    claude: { ...cur.claude, ...(patch.claude ?? {}) },
  };
  await fs.writeFile(FILE, JSON.stringify(next, null, 2), "utf8");
  return next;
}

/** UI-নিরাপদ ভিউ: API key গোপন রেখে শুধু "সেট আছে কি" জানায় */
export function redactSettings(s) {
  return {
    aiProvider: s.aiProvider,
    ollama: s.ollama,
    claude: { model: s.claude.model, apiKeySet: Boolean(s.claude.apiKey) },
  };
}
