// মেয়াদ/Entitlement যাচাই — behavior test (node:test)।
import { test } from "node:test";
import assert from "node:assert/strict";
import { bondDirectNonGarments as mod } from "../src/modules/bond-direct-non-garments.js";
import { runValidityChecks, validityResultToFinding } from "../src/checks/validity.js";

const byId = (results, id) => results.find((r) => r.id === id);

test("license expired → high flag", () => {
  const { results } = runValidityChecks(mod, {
    "val-license-expiry": { licenseExpiry: "2020-01-01", asOf: "2024-01-01" },
  });
  const r = byId(results, "val-license-expiry");
  assert.equal(r.status, "flag");
  assert.equal(r.severity, "high");
  assert.ok(r.detail.daysOverdue > 0);
});

test("license expiring within 90 days → medium flag", () => {
  const { results } = runValidityChecks(mod, {
    "val-license-expiry": { licenseExpiry: "2024-03-01", asOf: "2024-01-15" },
  });
  const r = byId(results, "val-license-expiry");
  assert.equal(r.status, "flag");
  assert.equal(r.severity, "medium");
});

test("license valid comfortably → ok", () => {
  const { results } = runValidityChecks(mod, {
    "val-license-expiry": { licenseExpiry: "2030-01-01", asOf: "2024-01-01" },
  });
  assert.equal(byId(results, "val-license-expiry").status, "ok");
});

test("license missing date → insufficient", () => {
  const { results } = runValidityChecks(mod, { "val-license-expiry": { asOf: "2024-01-01" } });
  assert.equal(byId(results, "val-license-expiry").status, "insufficient");
});

test("transaction outside UP validity → high flag", () => {
  const { results } = runValidityChecks(mod, {
    "val-up-coverage": { upValidFrom: "2024-01-01", upValidTo: "2024-12-31", transactionDate: "2025-02-01" },
  });
  const r = byId(results, "val-up-coverage");
  assert.equal(r.status, "flag");
  assert.equal(r.severity, "high");
});

test("transaction within UP validity → ok", () => {
  const { results } = runValidityChecks(mod, {
    "val-up-coverage": { upValidFrom: "2024-01-01", upValidTo: "2024-12-31", transactionDate: "2024-06-15" },
  });
  assert.equal(byId(results, "val-up-coverage").status, "ok");
});

test("HS code outside entitlement → flag lists offenders", () => {
  const { results } = runValidityChecks(mod, {
    "val-hs-entitlement": { entitledHs: "5208.11, 5208.12", importedHs: "5208.11 6109.10" },
  });
  const r = byId(results, "val-hs-entitlement");
  assert.equal(r.status, "flag");
  assert.deepEqual(r.detail.outside, ["6109.10"]);
});

test("all HS codes entitled → ok", () => {
  const { results } = runValidityChecks(mod, {
    "val-hs-entitlement": { entitledHs: "5208.11 5208.12 6109.10", importedHs: "5208.11, 6109.10" },
  });
  assert.equal(byId(results, "val-hs-entitlement").status, "ok");
});

test("validityResultToFinding maps flag → finding (revenue 0, source validity)", () => {
  const { results } = runValidityChecks(mod, { "val-license-expiry": { licenseExpiry: "2020-01-01", asOf: "2024-01-01" } });
  const f = validityResultToFinding(byId(results, "val-license-expiry"));
  assert.equal(f.revenueImplication, 0);
  assert.equal(f.source, "validity");
  assert.equal(f.checklistId, "lic-validity");
});
