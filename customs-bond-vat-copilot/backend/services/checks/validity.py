"""
মেয়াদ/Entitlement যাচাই — তারিখ ও HS-list ভিত্তিক (JS src/checks/validity.js হইতে পোর্ট)।
compliance flag — revenue হিসাব নেই (finding-এ revenue 0)।
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional


def _parse_date(s: Any) -> Optional[date]:
    if not s or not isinstance(s, str):
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _fmt(d: Optional[date]) -> str:
    return d.strftime("%Y-%m-%d") if d else "—"


def _tokenize_list(s: Any) -> list[str]:
    seen, out = set(), []
    for t in re.split(r"[^0-9A-Z.]+", str(s or "").upper()):
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _ok(sev: str, obs: str) -> dict:
    return {"status": "ok", "severity": sev or "low", "observation": obs, "detail": None}


def _flag(sev: str, obs: str, detail=None) -> dict:
    return {"status": "flag", "severity": sev, "observation": obs, "detail": detail}


def _insufficient(reason: str) -> dict:
    return {"status": "insufficient", "severity": "low", "observation": reason, "detail": None}


def _c_license_expiry(v: dict) -> dict:
    exp = _parse_date(v.get("licenseExpiry"))
    if not exp:
        return _insufficient("লাইসেন্স মেয়াদ শেষের তারিখ দিন (YYYY-MM-DD)।")
    as_of = _parse_date(v.get("asOf")) or date.today()
    days = (exp - as_of).days
    if days < 0:
        return _flag("high", f"বন্ড লাইসেন্স মেয়াদ {_fmt(exp)} — নিরীক্ষা তারিখ {_fmt(as_of)} অনুযায়ী "
                             f"{-days} দিন আগে উত্তীর্ণ। নবায়ন ছাড়া বন্ড কার্যক্রম অবৈধ।",
                     {"daysOverdue": -days})
    if days <= 90:
        return _flag("medium", f"বন্ড লাইসেন্স মেয়াদ {_fmt(exp)} — আর মাত্র {days} দিন বাকি; নবায়ন "
                               f"প্রক্রিয়া নিশ্চিত করুন।", {"daysLeft": days})
    return _ok("low", f"বন্ড লাইসেন্স {_fmt(exp)} পর্যন্ত বৈধ ({days} দিন বাকি)।")


def _c_up_coverage(v: dict) -> dict:
    frm = _parse_date(v.get("upValidFrom"))
    to = _parse_date(v.get("upValidTo"))
    txn = _parse_date(v.get("transactionDate"))
    if not frm or not to or not txn:
        return _insufficient("UP/UD বৈধতার শুরু-শেষ ও লেনদেন তারিখ দিন।")
    if txn < frm or txn > to:
        return _flag("high", f"লেনদেন তারিখ {_fmt(txn)} UP/UD/EP মেয়াদ ({_fmt(frm)}–{_fmt(to)})-এর বাইরে "
                             f"— এই সময়ে শুল্কমুক্ত সুবিধা প্রযোজ্য নয়।",
                     {"from": _fmt(frm), "to": _fmt(to), "txn": _fmt(txn)})
    return _ok("low", f"লেনদেন {_fmt(txn)} UP/UD মেয়াদের ({_fmt(frm)}–{_fmt(to)}) মধ্যে।")


def _c_hs_entitlement(v: dict) -> dict:
    ent = _tokenize_list(v.get("entitledHs"))
    imp = _tokenize_list(v.get("importedHs"))
    if not ent or not imp:
        return _insufficient("অনুমোদিত ও আমদানিকৃত HS code দিন।")
    ent_set = set(ent)
    outside = [c for c in imp if c not in ent_set]
    if outside:
        return _flag("high", f"entitlement-বহির্ভূত HS code আমদানি: {', '.join(outside)} — লাইসেন্সে "
                             f"অনুমোদিত নয়।", {"outside": outside})
    return _ok("low", f"সব আমদানিকৃত HS code ({len(imp)}টি) entitlement-এর মধ্যে।")


COMPUTERS = {
    "val-license-expiry": _c_license_expiry,
    "val-up-coverage": _c_up_coverage,
    "val-hs-entitlement": _c_hs_entitlement,
}


def run_validity_checks(specs: list[dict], inputs_by_check: Optional[dict] = None) -> dict:
    inputs_by_check = inputs_by_check or {}
    results = []
    for spec in specs:
        base = {"id": spec["id"], "title": spec.get("title", ""), "area": spec.get("area", ""),
                "legalRef": spec.get("legalRef")}
        compute = COMPUTERS.get(spec["id"])
        if not compute:
            results.append({**base, "status": "insufficient", "severity": "low",
                            "observation": "এই check-এর হিসাব এখনো যুক্ত হয়নি।"})
            continue
        results.append({**base, **compute(inputs_by_check.get(spec["id"]) or {})})
    flagged = [r for r in results if r["status"] == "flag"]
    return {"results": results, "summary": {"flagged": len(flagged)}}


def validity_result_to_finding(result: dict) -> dict:
    return {
        "checklistId": "lic-validity",
        "area": result.get("area", ""),
        "title": result.get("title", ""),
        "observation": result.get("observation", ""),
        "legalRef": result.get("legalRef"),
        "revenueImplication": 0,
        "severity": result.get("severity", "medium"),
        "source": "validity",
    }


__all__ = ["run_validity_checks", "validity_result_to_finding", "COMPUTERS"]
