// Smart Evidence Chip extraction — behavior test (node:test, zero-dependency)।
import { test } from "node:test";
import assert from "node:assert/strict";
import { bondDirectNonGarments as mod } from "../src/modules/bond-direct-non-garments.js";
import { extractDocument, scanDocuments } from "../src/checks/evidence.js";

const docWith = (text, over = {}) => ({ id: "doc_1", filename: "be.pdf", ocrStatus: "done", ocrText: text, ...over });
const chipFor = (chips, v) => chips.find((c) => c.value === v);

test("extracts ASCII numbers with thousands separators and decimals", () => {
  const { chips } = extractDocument(docWith("Total imported quantity 1,200.50 units under B/E"), mod);
  const c = chipFor(chips, 1200.5);
  assert.ok(c, "1,200.50 extracted");
  assert.equal(c.raw, "1,200.50");
  assert.equal(c.page, 1);
});

test("converts Bengali digits to value", () => {
  const { chips } = extractDocument(docWith("আমদানি পরিমাণ ১২৩৪ একক"), mod);
  assert.ok(chipFor(chips, 1234), "Bengali ১২৩৪ → 1234");
});

test("context-aware suggestion: 'আমদানি/B/E' → imported/beQty fields", () => {
  const { chips } = extractDocument(docWith("Bill of Entry আমদানি 1500 একক"), mod);
  const c = chipFor(chips, 1500);
  const keys = c.suggestions.map((s) => s.inputKey);
  assert.ok(keys.includes("imported") || keys.includes("beQty"), "suggests an import field");
  assert.ok(c.suggestions[0].score > 0, "top suggestion has positive score");
});

test("machinery context routes to the machinery register check, not raw", () => {
  const { chips } = extractDocument(docWith("মেশিনারিজ রেজিস্টার লিপিবদ্ধ 4 একক"), mod);
  const c = chipFor(chips, 4);
  const top = c.suggestions[0];
  assert.ok(top, "has a suggestion");
  assert.equal(top.checkId, "num-be-register-machinery");
  assert.equal(top.inputKey, "registerQty");
});

test("confidence rises with a unit/currency cue + field match", () => {
  const strong = extractDocument(docWith("অপচয় wastage declared ৳ 80 একক"), mod).chips.find((c) => c.value === 80);
  const bare = extractDocument(docWith("page 80"), mod).chips.find((c) => c.value === 80);
  assert.ok(strong.confidence > bare.confidence, "labelled+unit beats bare number");
  assert.ok(strong.confidence <= 1 && bare.confidence >= 0);
});

test("every chip carries full provenance fields", () => {
  const { chips } = extractDocument(docWith("closing stock সমাপনী মজুদ 200 একক"), mod);
  const c = chips[0];
  for (const k of ["id", "docId", "docFilename", "page", "value", "raw", "offset", "sourceText", "suggestions", "confidence"]) {
    assert.ok(k in c, `chip has ${k}`);
  }
  assert.equal(c.docFilename, "be.pdf");
  assert.ok(c.sourceText.length > 0);
});

test("page detection via form-feed", () => {
  const { chips } = extractDocument(docWith("opening 10 units\fclosing 20 units"), mod);
  assert.equal(chipFor(chips, 10).page, 1);
  assert.equal(chipFor(chips, 20).page, 2);
});

test("scanDocuments skips docs without OCR text", () => {
  const res = scanDocuments([
    docWith("imported 100 units", { id: "d1" }),
    { id: "d2", filename: "x.pdf", ocrStatus: "none", ocrText: "" },
  ], mod);
  assert.equal(res.scannedDocs, 1);
  assert.ok(res.totalChips >= 1);
});
