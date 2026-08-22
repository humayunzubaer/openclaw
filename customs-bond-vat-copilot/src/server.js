// Customs Bond & VAT Audit Copilot — লোকাল সার্ভার।
// শূন্য-নির্ভরতা: শুধু Node built-in মডিউল। চালান:  node src/server.js
// তারপর ব্রাউজারে খুলুন:  http://localhost:4700

import http from "node:http";
import os from "node:os";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import * as store from "./storage.js";
import { getModule, listModules } from "./modules/index.js";
import { isOcrAvailable, recognize } from "./ocr.js";
import { listProviders, draftFindings } from "./ai/index.js";
import { runNumericChecks, resultToFinding } from "./checks/numeric.js";
import { scanDocuments } from "./checks/evidence.js";
import { buildReport } from "./report/generate.js";
import { toWordDoc, toXlsx, toPrintablePdfHtml } from "./report/export.js";
import { getSettings, saveSettings, redactSettings } from "./settings.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.join(__dirname, "..", "public");
const PORT = process.env.PORT || 4700;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".webmanifest": "application/manifest+json; charset=utf-8",
  ".png": "image/png",
};

const json = (res, code, data) => {
  res.writeHead(code, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(data));
};

async function readBody(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function serveStatic(res, urlPath) {
  const rel = urlPath === "/" ? "index.html" : urlPath.replace(/^\/+/, "");
  const file = path.join(PUBLIC_DIR, rel);
  if (!file.startsWith(PUBLIC_DIR)) return json(res, 403, { error: "forbidden" });
  try {
    const buf = await fs.readFile(file);
    res.writeHead(200, { "Content-Type": MIME[path.extname(file)] ?? "application/octet-stream" });
    res.end(buf);
  } catch {
    res.writeHead(404, { "Content-Type": "text/plain" });
    res.end("Not found");
  }
}

// ---- Route table: [method, regex, handler(params, req, res)] ----
const routes = [
  ["GET", /^\/api\/modules$/, async (_p, _req, res) => json(res, 200, listModules())],
  ["GET", /^\/api\/providers$/, async (_p, _req, res) => json(res, 200, listProviders())],
  ["GET", /^\/api\/ocr-status$/, async (_p, _req, res) => json(res, 200, { available: await isOcrAvailable() })],

  ["GET", /^\/api\/audits$/, async (_p, _req, res) => json(res, 200, await store.listAudits())],
  ["POST", /^\/api\/audits$/, async (_p, req, res) => {
    const body = await readBody(req);
    if (!getModule(body.moduleId)) return json(res, 400, { error: "invalid moduleId" });
    json(res, 201, await store.createAudit(body));
  }],
  ["GET", /^\/api\/audits\/([^/]+)$/, async ([id], _req, res) => {
    const a = await store.getAudit(id);
    a ? json(res, 200, { audit: a, module: getModule(a.moduleId) }) : json(res, 404, { error: "not found" });
  }],
  ["PATCH", /^\/api\/audits\/([^/]+)$/, async ([id], req, res) => {
    const a = await store.updateAudit(id, await readBody(req));
    a ? json(res, 200, a) : json(res, 404, { error: "not found" });
  }],

  ["GET", /^\/api\/audits\/([^/]+)\/documents$/, async ([id], _req, res) => json(res, 200, await store.listDocuments(id))],
  ["POST", /^\/api\/audits\/([^/]+)\/documents$/, async ([id], req, res) => {
    const body = await readBody(req);
    if (!body.filename || !body.base64) return json(res, 400, { error: "filename and base64 required" });
    json(res, 201, await store.addDocument(id, body));
  }],
  ["GET", /^\/api\/audits\/([^/]+)\/documents\/([^/]+)\/file$/, async ([id, docId], _req, res) => {
    const found = await store.getDocumentFile(id, docId);
    if (!found) return json(res, 404, { error: "not found" });
    res.writeHead(200, { "Content-Type": "application/octet-stream", "Content-Disposition": `inline; filename="${found.doc.filename}"` });
    res.end(found.buf);
  }],
  ["POST", /^\/api\/audits\/([^/]+)\/documents\/([^/]+)\/ocr$/, async ([id, docId], _req, res) => {
    if (!(await isOcrAvailable())) return json(res, 501, { error: "OCR_NOT_INSTALLED", hint: "npm install tesseract.js" });
    const found = await store.getDocumentFile(id, docId);
    if (!found) return json(res, 404, { error: "not found" });
    try {
      const { text } = await recognize(found.buf);
      const doc = await store.updateDocument(id, docId, { ocrStatus: "done", ocrText: text });
      json(res, 200, doc);
    } catch (err) {
      await store.updateDocument(id, docId, { ocrStatus: "failed" });
      json(res, 500, { error: "ocr_failed", message: String(err?.message ?? err) });
    }
  }],

  ["GET", /^\/api\/audits\/([^/]+)\/findings$/, async ([id], _req, res) => json(res, 200, await store.listFindings(id))],
  ["POST", /^\/api\/audits\/([^/]+)\/findings$/, async ([id], req, res) => json(res, 201, await store.addFinding(id, await readBody(req)))],
  ["PATCH", /^\/api\/audits\/([^/]+)\/findings\/([^/]+)$/, async ([id, fid], req, res) => {
    const f = await store.updateFinding(id, fid, await readBody(req));
    f ? json(res, 200, f) : json(res, 404, { error: "not found" });
  }],
  ["DELETE", /^\/api\/audits\/([^/]+)\/findings\/([^/]+)$/, async ([id, fid], _req, res) => {
    json(res, 200, { deleted: await store.deleteFinding(id, fid) });
  }],

  ["POST", /^\/api\/audits\/([^/]+)\/analyze$/, async ([id], req, res) => {
    const body = await readBody(req);
    const audit = await store.getAudit(id);
    const module = getModule(audit?.moduleId);
    if (!module) return json(res, 404, { error: "not found" });
    const documents = await store.listDocuments(id);
    const settings = await getSettings();
    const provider = body.provider ?? settings.aiProvider ?? "none";
    try {
      const result = await draftFindings(provider, { module, documents, settings });
      json(res, 200, result);
    } catch (err) {
      json(res, 502, { error: "analysis_failed", message: String(err?.message ?? err) });
    }
  }],

  // সংখ্যাগত auto-check
  ["GET", /^\/api\/audits\/([^/]+)\/numeric$/, async ([id], _req, res) => {
    const audit = await store.getAudit(id);
    const module = getModule(audit?.moduleId);
    if (!module) return json(res, 404, { error: "not found" });
    const saved = await store.getNumeric(id);
    json(res, 200, { specs: module.numericChecks ?? [], inputs: saved.inputs, results: saved.results, summary: saved.summary });
  }],
  ["POST", /^\/api\/audits\/([^/]+)\/numeric$/, async ([id], req, res) => {
    const audit = await store.getAudit(id);
    const module = getModule(audit?.moduleId);
    if (!module) return json(res, 404, { error: "not found" });
    const { inputs } = await readBody(req);
    const { results, summary } = runNumericChecks(module, inputs ?? {});
    await store.saveNumeric(id, { inputs: inputs ?? {}, results, summary });
    // manual override হলে stale evidence-provenance বাদ দিই (badge সৎ রাখতে; log অক্ষত)
    const ev = await store.getEvidence(id);
    let pruned = false;
    for (const key of Object.keys(ev.applied)) {
      const [cId, iKey] = key.split("::");
      const cur = inputs?.[cId]?.[iKey];
      if (cur === undefined || Number(cur) !== Number(ev.applied[key].value)) { delete ev.applied[key]; pruned = true; }
    }
    if (pruned) await store.saveEvidence(id, ev);
    json(res, 200, { results, summary });
  }],
  // Smart Evidence Chip: OCR টেক্সট থেকে সংখ্যা extract (context-aware suggestion সহ)
  ["POST", /^\/api\/audits\/([^/]+)\/evidence\/scan$/, async ([id], req, res) => {
    const audit = await store.getAudit(id);
    const module = getModule(audit?.moduleId);
    if (!module) return json(res, 404, { error: "not found" });
    const { docId } = await readBody(req);
    const docs = await store.listDocuments(id);
    const target = docId ? docs.filter((d) => d.id === docId) : docs;
    json(res, 200, scanDocuments(target, module));
  }],
  // একটি chip → numeric field-এ প্রয়োগ + provenance ও audit trail লিপিবদ্ধ
  ["POST", /^\/api\/audits\/([^/]+)\/evidence\/apply$/, async ([id], req, res) => {
    const audit = await store.getAudit(id);
    const module = getModule(audit?.moduleId);
    if (!module) return json(res, 404, { error: "not found" });
    const { chip, checkId, inputKey } = await readBody(req);
    const check = (module.numericChecks ?? []).find((c) => c.id === checkId);
    const input = check?.inputs.find((i) => i.key === inputKey);
    if (!check || !input) return json(res, 400, { error: "invalid check/input" });
    if (!chip || typeof chip.value !== "number") return json(res, 400, { error: "chip.value (number) required" });

    const numeric = await store.getNumeric(id);
    const inputs = numeric.inputs ?? {};
    (inputs[checkId] ??= {})[inputKey] = chip.value;
    const { results, summary } = runNumericChecks(module, inputs);
    await store.saveNumeric(id, { inputs, results, summary });

    const key = `${checkId}::${inputKey}`;
    const suggestion = (chip.suggestions ?? []).find((s) => s.checkId === checkId && s.inputKey === inputKey);
    const ev = await store.getEvidence(id);
    const prev = ev.applied[key] ?? null;
    const record = {
      checkId, inputKey, checkTitle: check.title, inputLabel: input.label,
      value: chip.value, raw: chip.raw ?? String(chip.value),
      docId: chip.docId ?? null, docFilename: chip.docFilename ?? null, page: chip.page ?? null,
      sourceText: chip.sourceText ?? "", confidence: chip.confidence ?? null,
      suggestionScore: suggestion?.score ?? null,
      auditor: audit.auditor || "", appliedAt: new Date().toISOString(),
    };
    ev.applied[key] = record;
    ev.log.push({ action: prev ? "override" : "apply", prevValue: prev?.value ?? null, ...record });
    await store.saveEvidence(id, ev);
    json(res, 200, { numeric: { results, summary }, applied: record });
  }],
  ["GET", /^\/api\/audits\/([^/]+)\/evidence$/, async ([id], _req, res) => json(res, 200, await store.getEvidence(id))],
  // flag হওয়া numeric result → finding (ডুপ্লিকেট এড়াতে একই title-এর numeric finding থাকলে skip)
  ["POST", /^\/api\/audits\/([^/]+)\/numeric\/to-findings$/, async ([id], req, res) => {
    const { checkIds } = await readBody(req);
    const saved = await store.getNumeric(id);
    const wanted = Array.isArray(checkIds) && checkIds.length ? new Set(checkIds) : null;
    const existing = await store.listFindings(id);
    const seen = new Set(existing.filter((f) => f.source === "numeric").map((f) => f.title));
    let added = 0, skipped = 0;
    for (const r of saved.results ?? []) {
      if (r.status !== "flag") continue;
      if (wanted && !wanted.has(r.id)) continue;
      if (seen.has(r.title)) { skipped++; continue; }
      await store.addFinding(id, resultToFinding(r));
      seen.add(r.title);
      added++;
    }
    json(res, 200, { added, skipped });
  }],

  ["GET", /^\/api\/audits\/([^/]+)\/working-paper$/, async ([id], _req, res) => json(res, 200, await store.getWorkingPaper(id))],
  ["PUT", /^\/api\/audits\/([^/]+)\/working-paper$/, async ([id], req, res) => json(res, 200, await store.saveWorkingPaper(id, await readBody(req)))],

  ["GET", /^\/api\/audits\/([^/]+)\/report\/([^/]+)$/, async ([id, kind], _req, res) => {
    const audit = await store.getAudit(id);
    const module = getModule(audit?.moduleId);
    if (!module) return json(res, 404, { error: "not found" });
    const [findings, documents, workingPaper, numeric] = await Promise.all([
      store.listFindings(id),
      store.listDocuments(id),
      store.getWorkingPaper(id),
      store.getNumeric(id),
    ]);
    try {
      const markdown = buildReport(kind, { audit, module, findings, documents, workingPaper, numeric });
      json(res, 200, { kind, markdown });
    } catch (err) {
      json(res, 400, { error: String(err?.message ?? err) });
    }
  }],

  ["GET", /^\/api\/audits\/([^/]+)\/export\/(word|excel|pdf)$/, async ([id, format], _req, res) => {
    const audit = await store.getAudit(id);
    const module = getModule(audit?.moduleId);
    if (!module) return json(res, 404, { error: "not found" });
    const [findings, documents, workingPaper, numeric] = await Promise.all([
      store.listFindings(id),
      store.listDocuments(id),
      store.getWorkingPaper(id),
      store.getNumeric(id),
    ]);
    const ctx = { audit, module, findings, documents, workingPaper, numeric };
    const slug = (audit.institution || "audit").replace(/[^\wঀ-৿]+/g, "_");

    if (format === "excel") {
      const buf = toXlsx(ctx);
      res.writeHead(200, {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": `attachment; filename="${slug}.xlsx"`,
      });
      return res.end(buf);
    }
    if (format === "word") {
      res.writeHead(200, {
        "Content-Type": "application/msword; charset=utf-8",
        "Content-Disposition": `attachment; filename="${slug}.doc"`,
      });
      return res.end(toWordDoc(ctx));
    }
    // pdf → print-ready HTML (browser Save-as-PDF), offline
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(toPrintablePdfHtml(ctx));
  }],

  ["GET", /^\/api\/settings$/, async (_p, _req, res) => json(res, 200, redactSettings(await getSettings()))],
  ["PUT", /^\/api\/settings$/, async (_p, req, res) => {
    const patch = await readBody(req);
    // খালি apiKey পাঠালে পুরনোটা মুছে ফেলা এড়াতে বাদ দিই
    if (patch.claude && !patch.claude.apiKey) delete patch.claude.apiKey;
    json(res, 200, redactSettings(await saveSettings(patch)));
  }],
];

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const pathname = decodeURIComponent(url.pathname);

    if (pathname.startsWith("/api/")) {
      for (const [method, rx, handler] of routes) {
        if (req.method !== method) continue;
        const m = pathname.match(rx);
        if (m) return await handler(m.slice(1), req, res);
      }
      return json(res, 404, { error: "unknown endpoint", path: pathname });
    }
    return await serveStatic(res, pathname);
  } catch (err) {
    json(res, 500, { error: "server_error", message: String(err?.message ?? err) });
  }
});

// একই Wi-Fi-তে ফোন/অন্য ডিভাইস থেকে ঢোকার জন্য এই কম্পিউটারের LAN ঠিকানা।
function lanAddresses() {
  const out = [];
  for (const list of Object.values(os.networkInterfaces())) {
    for (const ni of list ?? []) {
      if (ni.family === "IPv4" && !ni.internal) out.push(ni.address);
    }
  }
  return out;
}

// 0.0.0.0 = সব ইন্টারফেস, যাতে ফোন থেকেও পৌঁছানো যায় (লোকাল Wi-Fi-এর মধ্যেই)।
server.listen(PORT, "0.0.0.0", () => {
  console.log(`\n  Customs Bond & VAT Audit Copilot`);
  console.log(`  এই কম্পিউটারে:  http://localhost:${PORT}`);
  const lan = lanAddresses();
  if (lan.length) {
    console.log(`\n  📱 মোবাইল/ট্যাবে (একই Wi-Fi):`);
    for (const ip of lan) console.log(`      http://${ip}:${PORT}`);
    console.log(`\n  (ফোনের ব্রাউজারে উপরের ঠিকানা টাইপ করুন)`);
  }
  console.log("");
});
