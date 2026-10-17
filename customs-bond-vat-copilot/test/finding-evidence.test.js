// Evidence ↔ Finding page-level linking — storage + report citation (node:test)।
import { test, after } from "node:test";
import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import path from "node:path";
import * as store from "../src/storage.js";
import { buildWorkingPaper, buildFinalReport } from "../src/report/generate.js";
import { bondDirectNonGarments as module } from "../src/modules/bond-direct-non-garments.js";

const created = [];
async function freshAudit() {
  const a = await store.createAudit({ institution: "Ev Co", moduleId: module.id, auditor: "T" });
  created.push(a.id);
  return a.id;
}
after(async () => {
  for (const id of created) await fs.rm(path.join(store.AUDITS_ROOT, id), { recursive: true, force: true });
});

test("addFinding stores page-level evidence and derives evidenceDocIds", async () => {
  const id = await freshAudit();
  const f = await store.addFinding(id, {
    title: "T", area: "স্টক", severity: "high", revenueImplication: 100,
    evidence: [
      { docId: "d1", docFilename: "be.pdf", page: 3, sourceText: "imported 1200", confidence: 0.9 },
      { docId: "d1", docFilename: "be.pdf", page: 5 },
      { docFilename: "loose.pdf" }, // no docId still kept
    ],
  });
  assert.equal(f.evidence.length, 3);
  assert.equal(f.evidence[0].page, 3);
  assert.deepEqual(f.evidenceDocIds, ["d1"]); // unique docIds
});

test("addFinding drops entries with neither docId nor filename", async () => {
  const id = await freshAudit();
  const f = await store.addFinding(id, { title: "T", evidence: [{ page: 2 }, { docId: "x" }] });
  assert.equal(f.evidence.length, 1);
  assert.equal(f.evidence[0].docId, "x");
});

test("updateFinding replaces evidence and refreshes evidenceDocIds", async () => {
  const id = await freshAudit();
  const f = await store.addFinding(id, { title: "T", evidence: [{ docId: "a", docFilename: "a.pdf", page: 1 }] });
  const u = await store.updateFinding(id, f.id, { evidence: [{ docId: "b", docFilename: "b.pdf", page: 9 }] });
  assert.equal(u.evidence.length, 1);
  assert.equal(u.evidence[0].docId, "b");
  assert.deepEqual(u.evidenceDocIds, ["b"]);
});

test("reports cite document + page from finding.evidence", () => {
  const findings = [{
    id: "f1", title: "অহিসাবকৃত", area: "স্টক ও উদ্বৃত্ত", observation: "ঘাটতি", severity: "high",
    revenueImplication: 3000, legalRef: "customs-act-156",
    evidence: [{ docId: "d1", docFilename: "register.pdf", page: 7, sourceText: "closing 200" }],
  }];
  const ctx = { audit: { institution: "X" }, module, findings, documents: [], workingPaper: { sections: {} }, numeric: null };
  const wp = buildWorkingPaper(ctx);
  const fin = buildFinalReport(ctx);
  assert.ok(wp.includes("register.pdf (পৃ.7)"), "working paper cites doc+page");
  assert.ok(fin.includes("register.pdf (পৃ.7)"), "final report cites doc+page");
});
