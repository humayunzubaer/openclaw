// সংখ্যাগত ইঞ্জিনের behavior test — শূন্য-নির্ভরতা (node:test)।
// চালান:  node --test
import { test } from "node:test";
import assert from "node:assert/strict";
import { bondDirectNonGarments as mod } from "../src/modules/bond-direct-non-garments.js";
import { runNumericChecks, resultToFinding } from "../src/checks/numeric.js";

const byId = (results, id) => results.find((r) => r.id === id);

test("entitlement breach → excess × duty", () => {
  const { results } = runNumericChecks(mod, {
    "num-entitlement": { approvedEntitlement: 1000, imported: 1200, dutyPerUnit: 50 },
  });
  const r = byId(results, "num-entitlement");
  assert.equal(r.status, "flag");
  assert.equal(r.severity, "high");
  assert.equal(r.discrepancy, 200);
  assert.equal(r.revenueImplication, 10000);
});

test("entitlement within limit → ok, no revenue", () => {
  const { results } = runNumericChecks(mod, {
    "num-entitlement": { approvedEntitlement: 1000, imported: 900, dutyPerUnit: 50 },
  });
  const r = byId(results, "num-entitlement");
  assert.equal(r.status, "ok");
  assert.equal(r.revenueImplication, 0);
});

test("B/E vs register: under-recording → diff × duty, high", () => {
  const { results } = runNumericChecks(mod, {
    "num-be-register": { beQty: 1000, registerQty: 850, dutyPerUnit: 30 },
  });
  const r = byId(results, "num-be-register");
  assert.equal(r.status, "flag");
  assert.equal(r.severity, "high");
  assert.equal(r.discrepancy, 150);
  assert.equal(r.revenueImplication, 4500);
});

test("B/E vs register: over-recording → medium flag, no revenue", () => {
  const { results } = runNumericChecks(mod, {
    "num-be-register": { beQty: 800, registerQty: 900, dutyPerUnit: 30 },
  });
  const r = byId(results, "num-be-register");
  assert.equal(r.status, "flag");
  assert.equal(r.severity, "medium");
  assert.equal(r.revenueImplication, 0);
});

test("B/E vs register: exact match → ok", () => {
  const { results } = runNumericChecks(mod, {
    "num-be-register": { beQty: 900, registerQty: 900, dutyPerUnit: 30 },
  });
  assert.equal(byId(results, "num-be-register").status, "ok");
});

test("UD vs export: unsupported consumption → × duty, high", () => {
  const { results } = runNumericChecks(mod, {
    "num-ud-export": { udClaimedRaw: 500, exportBackedRaw: 420, dutyPerRawUnit: 15 },
  });
  const r = byId(results, "num-ud-export");
  assert.equal(r.status, "flag");
  assert.equal(r.discrepancy, 80);
  assert.equal(r.revenueImplication, 1200);
});

test("UD vs export: fully supported → ok", () => {
  const { results } = runNumericChecks(mod, {
    "num-ud-export": { udClaimedRaw: 400, exportBackedRaw: 400, dutyPerRawUnit: 15 },
  });
  assert.equal(byId(results, "num-ud-export").status, "ok");
});

test("coefficient overconsumption", () => {
  const { results } = runNumericChecks(mod, {
    "num-coefficient": { finishedProduced: 100, coeffPerUnit: 2, actualConsumed: 250, dutyPerRawUnit: 10 },
  });
  const r = byId(results, "num-coefficient");
  assert.equal(r.status, "flag");
  assert.equal(r.discrepancy, 50); // 250 - (100*2)
  assert.equal(r.revenueImplication, 500);
});

test("material balance shortage → unaccounted × duty, high", () => {
  const { results } = runNumericChecks(mod, {
    "num-material-balance": {
      openingStock: 100, imported: 1000, consumedForExport: 700,
      wastageAllowedQty: 50, closingStock: 200, dutyPerRawUnit: 20,
    },
  });
  const r = byId(results, "num-material-balance");
  // (100+1000) - (700+50+200) = 150
  assert.equal(r.status, "flag");
  assert.equal(r.severity, "high");
  assert.equal(r.discrepancy, 150);
  assert.equal(r.revenueImplication, 3000);
});

test("material balance exact → ok", () => {
  const { results } = runNumericChecks(mod, {
    "num-material-balance": {
      openingStock: 0, imported: 1000, consumedForExport: 900,
      wastageAllowedQty: 50, closingStock: 50, dutyPerRawUnit: 20,
    },
  });
  assert.equal(byId(results, "num-material-balance").status, "ok");
});

test("material balance over-accounting → medium flag, no revenue", () => {
  const { results } = runNumericChecks(mod, {
    "num-material-balance": {
      openingStock: 0, imported: 1000, consumedForExport: 1100,
      closingStock: 0, dutyPerRawUnit: 20,
    },
  });
  const r = byId(results, "num-material-balance");
  assert.equal(r.status, "flag");
  assert.equal(r.severity, "medium");
  assert.equal(r.revenueImplication, 0);
});

test("wastage over allowed rate", () => {
  const { results } = runNumericChecks(mod, {
    "num-wastage": { consumedRaw: 1000, allowedWastagePct: 5, declaredWastageQty: 80, dutyPerRawUnit: 10 },
  });
  const r = byId(results, "num-wastage");
  // allowed = 50; excess = 30
  assert.equal(r.discrepancy, 30);
  assert.equal(r.revenueImplication, 300);
});

test("overstay → qty × duty, medium", () => {
  const { results } = runNumericChecks(mod, {
    "num-overstay": { overstayQty: 40, dutyPerRawUnit: 25 },
  });
  const r = byId(results, "num-overstay");
  assert.equal(r.status, "flag");
  assert.equal(r.severity, "medium");
  assert.equal(r.revenueImplication, 1000);
});

test("missing required input → insufficient (not a false 'ok')", () => {
  const { results } = runNumericChecks(mod, {
    "num-entitlement": { imported: 1200 }, // approvedEntitlement missing
  });
  assert.equal(byId(results, "num-entitlement").status, "insufficient");
});

test("duty omitted → quantity flagged, revenue 0", () => {
  const { results } = runNumericChecks(mod, {
    "num-entitlement": { approvedEntitlement: 1000, imported: 1200 },
  });
  const r = byId(results, "num-entitlement");
  assert.equal(r.status, "flag");
  assert.equal(r.discrepancy, 200);
  assert.equal(r.revenueImplication, 0);
});

test("summary totals only count flagged revenue", () => {
  const { summary } = runNumericChecks(mod, {
    "num-entitlement": { approvedEntitlement: 1000, imported: 1200, dutyPerUnit: 50 }, // 10000
    "num-overstay": { overstayQty: 40, dutyPerRawUnit: 25 }, // 1000
    "num-coefficient": { finishedProduced: 100, coeffPerUnit: 2, actualConsumed: 150, dutyPerRawUnit: 10 }, // ok
  });
  assert.equal(summary.flagged, 2);
  assert.equal(summary.totalRevenue, 11000);
});

test("resultToFinding maps a flag into finding shape", () => {
  const { results } = runNumericChecks(mod, {
    "num-overstay": { overstayQty: 40, dutyPerRawUnit: 25 },
  });
  const f = resultToFinding(byId(results, "num-overstay"));
  assert.equal(f.revenueImplication, 1000);
  assert.equal(f.legalRef, "bwl-rules");
  assert.equal(f.source, "numeric");
});
