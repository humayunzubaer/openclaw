// স্টোরেজ স্তর — প্রতিটি অডিট একটি স্বয়ংসম্পূর্ণ ফোল্ডার।
// কোনো ডেটাবেস সার্ভার লাগে না; সবকিছু ফাইলে, তাই পোর্টেবল ও ইন্সপেক্টেবল।
//
// audits/<auditId>/
//   audit.json        — মেটাডেটা (প্রতিষ্ঠান, টাইপ, স্ট্যাটাস, তারিখ)
//   documents/        — আপলোড করা মূল নথি
//   documents.json    — নথি রেজিস্ট্রি (id, filename, category, ocrText)
//   findings.json     — অসঙ্গতি/finding তালিকা
//   evidence.json     — finding ↔ নথি/পৃষ্ঠা লিংক
//   working-paper.json— ওয়ার্কিং পেপার সেকশন ও নোট
//   report/           — তৈরি করা রিপোর্ট

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const AUDITS_ROOT = path.join(__dirname, "..", "audits");

const newId = (prefix) => `${prefix}_${Date.now().toString(36)}_${crypto.randomBytes(3).toString("hex")}`;

async function readJson(file, fallback) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch (err) {
    if (err.code === "ENOENT") return fallback;
    throw err;
  }
}

async function writeJson(file, data) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify(data, null, 2), "utf8");
}

const auditDir = (id) => path.join(AUDITS_ROOT, id);
const paths = (id) => ({
  meta: path.join(auditDir(id), "audit.json"),
  docsMeta: path.join(auditDir(id), "documents.json"),
  docsDir: path.join(auditDir(id), "documents"),
  findings: path.join(auditDir(id), "findings.json"),
  evidence: path.join(auditDir(id), "evidence.json"),
  workingPaper: path.join(auditDir(id), "working-paper.json"),
  reportDir: path.join(auditDir(id), "report"),
});

// ---- Audits ----

export async function listAudits() {
  await fs.mkdir(AUDITS_ROOT, { recursive: true });
  const entries = await fs.readdir(AUDITS_ROOT, { withFileTypes: true });
  const audits = [];
  for (const e of entries) {
    if (!e.isDirectory()) continue;
    const meta = await readJson(paths(e.name).meta, null);
    if (meta) audits.push(meta);
  }
  return audits.sort((a, b) => (b.createdAt ?? "").localeCompare(a.createdAt ?? ""));
}

export async function createAudit({ institution, moduleId, period, auditor }) {
  const id = newId("audit");
  const now = new Date().toISOString();
  const meta = {
    id,
    institution: institution ?? "",
    moduleId,
    period: period ?? "",
    auditor: auditor ?? "",
    status: "in-progress",
    createdAt: now,
    updatedAt: now,
  };
  await writeJson(paths(id).meta, meta);
  await fs.mkdir(paths(id).docsDir, { recursive: true });
  return meta;
}

export async function getAudit(id) {
  return readJson(paths(id).meta, null);
}

export async function updateAudit(id, patch) {
  const meta = await getAudit(id);
  if (!meta) return null;
  const next = { ...meta, ...patch, id, updatedAt: new Date().toISOString() };
  await writeJson(paths(id).meta, next);
  return next;
}

// ---- Documents ----

export async function listDocuments(auditId) {
  return readJson(paths(auditId).docsMeta, []);
}

/** base64 কন্টেন্টসহ নথি সংরক্ষণ (UI থেকে JSON POST হিসেবে আসে) */
export async function addDocument(auditId, { filename, category, base64 }) {
  const p = paths(auditId);
  const docId = newId("doc");
  const safeName = `${docId}__${filename.replace(/[^\w.\-]+/g, "_")}`;
  await fs.mkdir(p.docsDir, { recursive: true });
  await fs.writeFile(path.join(p.docsDir, safeName), Buffer.from(base64, "base64"));

  const docs = await listDocuments(auditId);
  const doc = {
    id: docId,
    filename,
    storedName: safeName,
    category: category ?? "uncategorized",
    ocrStatus: "none", // none | done | failed
    ocrText: "",
    uploadedAt: new Date().toISOString(),
  };
  docs.push(doc);
  await writeJson(p.docsMeta, docs);
  return doc;
}

export async function getDocumentFile(auditId, docId) {
  const docs = await listDocuments(auditId);
  const doc = docs.find((d) => d.id === docId);
  if (!doc) return null;
  const buf = await fs.readFile(path.join(paths(auditId).docsDir, doc.storedName));
  return { doc, buf };
}

export async function updateDocument(auditId, docId, patch) {
  const docs = await listDocuments(auditId);
  const idx = docs.findIndex((d) => d.id === docId);
  if (idx === -1) return null;
  docs[idx] = { ...docs[idx], ...patch, id: docId };
  await writeJson(paths(auditId).docsMeta, docs);
  return docs[idx];
}

// ---- Findings ----

export async function listFindings(auditId) {
  return readJson(paths(auditId).findings, []);
}

export async function addFinding(auditId, finding) {
  const findings = await listFindings(auditId);
  const item = {
    id: newId("find"),
    checklistId: finding.checklistId ?? null,
    area: finding.area ?? "",
    title: finding.title ?? "",
    observation: finding.observation ?? "",
    legalRef: finding.legalRef ?? null,
    revenueImplication: finding.revenueImplication ?? 0,
    severity: finding.severity ?? "medium", // low | medium | high
    evidenceDocIds: finding.evidenceDocIds ?? [],
    createdAt: new Date().toISOString(),
  };
  findings.push(item);
  await writeJson(paths(auditId).findings, findings);
  return item;
}

export async function updateFinding(auditId, findingId, patch) {
  const findings = await listFindings(auditId);
  const idx = findings.findIndex((f) => f.id === findingId);
  if (idx === -1) return null;
  findings[idx] = { ...findings[idx], ...patch, id: findingId };
  await writeJson(paths(auditId).findings, findings);
  return findings[idx];
}

export async function deleteFinding(auditId, findingId) {
  const findings = await listFindings(auditId);
  const next = findings.filter((f) => f.id !== findingId);
  await writeJson(paths(auditId).findings, next);
  return next.length !== findings.length;
}

// ---- Working paper ----

export async function getWorkingPaper(auditId) {
  return readJson(paths(auditId).workingPaper, { sections: {} });
}

export async function saveWorkingPaper(auditId, data) {
  await writeJson(paths(auditId).workingPaper, data);
  return data;
}

export { paths };
