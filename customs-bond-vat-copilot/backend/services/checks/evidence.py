"""
Smart Evidence Chip extraction — context-aware (JS src/checks/evidence.js হইতে পোর্ট)।

generic number নয়: প্রতিটি extracted value একটি Evidence Chip — document+page,
আশপাশের OCR স্নিপেট, কোন check-input-এ বসবে তার সাজেশন (বাংলা+English synonym,
দুই-স্তর keyword), confidence। auto-map নয় — টুল সাজেশন দেয়, নিরীক্ষক প্রয়োগ করেন।
"""
from __future__ import annotations

import re
from typing import Any

_BN = "০১২৩৪৫৬৭৮৯"


def _bn_to_ascii(s: str) -> str:
    return "".join(str(_BN.index(c)) if c in _BN else c for c in s)


def _r2(n: float) -> float:
    return round(float(n), 2)


def _clamp01(n: float) -> float:
    return max(0.0, min(1.0, n))


# ASCII/বাংলা অঙ্ক, thousands (,) ও দশমিক (.)সহ
_NUM_RE = re.compile(r"[0-9০-৯][0-9০-৯,]*(?:\.[0-9০-৯]+)?")

SYN = {
    "approvedEntitlement": ["entitlement", "up", "utilization permission", "অনুমোদিত", "এনটাইটেলমেন্ট", "প্রাপ্যতা"],
    "imported": ["import", "imported", "আমদানি", "bill of entry", "b/e", "be"],
    "dutyPerUnit": ["duty", "tax", "শুল্ক", "কর", "রাজস্ব", "rate", "হার"],
    "finishedProduced": ["finished", "production", "produced", "উৎপাদন", "উৎপাদিত", "পণ্য"],
    "coeffPerUnit": ["coefficient", "coeff", "input-output", "গুণাঙ্ক", "হার"],
    "actualConsumed": ["consumed", "consumption", "ব্যবহার", "ব্যবহৃত", "খরচ"],
    "dutyPerRawUnit": ["duty", "tax", "শুল্ক", "কর", "রাজস্ব", "rate"],
    "beQty": ["bill of entry", "b/e", "be", "আমদানি", "imported"],
    "registerQty": ["register", "রেজিস্টার", "রেজিস্ট্রার", "recorded", "লিপিবদ্ধ", "ইন-টু-বন্ড", "in-bond"],
    "udClaimedRaw": ["ud", "up", "ep", "utilization declaration", "sales contract", "claimed", "দাবি", "দাবিকৃত"],
    "exportBackedRaw": ["export", "রপ্তানি", "bill of export", "exported"],
    "openingStock": ["opening", "প্রারম্ভিক", "opening stock", "প্রারম্ভিক মজুদ", "মজুদ"],
    "consumedForExport": ["consumed", "export", "রপ্তানি", "ব্যবহৃত"],
    "wastageAllowedQty": ["wastage", "অপচয়", "waste", "allowed"],
    "closingStock": ["closing", "সমাপনী", "closing stock", "সমাপনী মজুদ", "মজুদ"],
    "allowedWastagePct": ["wastage", "অপচয়", "percent", "হার", "rate"],
    "consumedRaw": ["consumed", "ব্যবহৃত", "consumption", "ব্যবহার"],
    "declaredWastageQty": ["wastage", "অপচয়", "declared", "দাবিকৃত"],
    "overstayQty": ["overstay", "মেয়াদোত্তীর্ণ", "expired", "overdue", "মেয়াদ"],
}

_UNIT_CUES = ["৳", "bdt", "টাকা", "একক", "kg", "kgs", "mt", "%", "pcs", "pc", "unit", "পিস", "yds", "gm"]
_STOP = {"vs", "এবং", "and", "the", "of", "—", "-", "b/e"}

# ASCII + Bengali block + / % — বাংলা যুক্তবর্ণ/মাত্রা অক্ষুণ্ণ রাখে
_TOK_RE = re.compile(r"[^0-9A-Za-zঀ-৿/%]+")


def _tokens(s: Any) -> list[str]:
    out = []
    for t in _TOK_RE.split(str(s or "").lower()):
        t = t.strip()
        if len(t) >= 2 and t not in _STOP:
            out.append(t)
    return out


def build_keyword_index(module_numeric_checks: list[dict]) -> list[dict]:
    checks = []
    for check in module_numeric_checks or []:
        title_toks = set(_tokens(check.get("title", "")) + _tokens(check.get("area", "")))
        check_keywords = [(t, 0.5) for t in title_toks]
        inputs = []
        for inp in check["inputs"]:
            kw: dict[str, float] = {}
            for s in SYN.get(inp["key"], []):
                k = s.lower()
                kw[k] = max(kw.get(k, 0.0), 0.35)
            for t in _tokens(inp["label"]):
                if t not in title_toks:
                    kw[t] = max(kw.get(t, 0.0), 0.3)
            inputs.append({"inputKey": inp["key"], "inputLabel": inp["label"], "keywords": list(kw.items())})
        checks.append({"checkId": check["id"], "checkTitle": check["title"],
                       "checkKeywords": check_keywords, "inputs": inputs})
    return checks


def _suggest_fields(context_lower: str, keyword_index: list[dict]) -> list[dict]:
    scored = []
    for check in keyword_index:
        check_score = sum(w for kw, w in check["checkKeywords"] if kw in context_lower)
        for inp in check["inputs"]:
            input_score = sum(w for kw, w in inp["keywords"] if kw in context_lower)
            if input_score <= 0.15:
                continue
            combined = input_score + 0.4 * check_score
            scored.append({"checkId": check["checkId"], "checkTitle": check["checkTitle"],
                           "inputKey": inp["inputKey"], "inputLabel": inp["inputLabel"],
                           "combined": combined, "score": _r2(_clamp01(combined))})
    scored.sort(key=lambda s: s["combined"], reverse=True)
    return [{k: v for k, v in s.items() if k != "combined"} for s in scored[:3]]


def _token_quality(raw: str) -> float:
    digits = len(re.sub(r"[^0-9০-৯]", "", raw))
    if "." in raw or "," in raw:
        return 0.9
    if digits >= 2:
        return 0.7
    return 0.4


def _extract_from_text(text: str, page: int, keyword_index: list[dict], ctx: dict) -> list[dict]:
    chips = []
    src = str(text or "")
    for m in _NUM_RE.finditer(src):
        raw = m.group(0)
        normalized = _bn_to_ascii(raw).replace(",", "")
        if normalized.count(".") > 1:
            continue
        try:
            value = float(normalized)
        except ValueError:
            continue
        start = max(0, m.start() - 45)
        end = min(len(src), m.start() + len(raw) + 45)
        source_text = re.sub(r"\s+", " ", src[start:end]).strip()
        lower = source_text.lower()
        suggestions = _suggest_fields(lower, keyword_index)
        field_score = suggestions[0]["score"] if suggestions else 0.0
        unit_cue = 0.15 if any(u in lower for u in _UNIT_CUES) else 0.0
        confidence = _r2(_clamp01(0.45 * _token_quality(raw) + 0.45 * field_score + unit_cue))
        chips.append({
            "id": f"chip_{ctx['docId']}_{page}_{m.start()}",
            "docId": ctx["docId"], "docFilename": ctx["docFilename"], "page": page,
            "value": _r2(value), "raw": raw, "offset": m.start(),
            "sourceText": source_text, "suggestions": suggestions, "confidence": confidence,
        })
    return chips


def extract_document(doc: dict, numeric_checks: list[dict], max_chips: int = 250) -> dict:
    keyword_index = build_keyword_index(numeric_checks)
    pages = str(doc.get("ocrText") or "").split("\f")
    chips: list[dict] = []
    for i, page_text in enumerate(pages):
        for c in _extract_from_text(page_text, i + 1, keyword_index,
                                    {"docId": doc["id"], "docFilename": doc.get("filename", "")}):
            chips.append(c)
            if len(chips) >= max_chips:
                break
        if len(chips) >= max_chips:
            break
    chips.sort(key=lambda c: (-c["confidence"], c["offset"]))
    return {"docId": doc["id"], "filename": doc.get("filename", ""), "chips": chips}


def scan_documents(documents: list[dict], numeric_checks: list[dict]) -> dict:
    groups = []
    for doc in documents or []:
        if doc.get("ocrStatus") not in (None, "done") or not str(doc.get("ocrText") or "").strip():
            continue
        g = extract_document(doc, numeric_checks)
        if g["chips"]:
            groups.append(g)
    total = sum(len(g["chips"]) for g in groups)
    return {"groups": groups, "totalChips": total, "scannedDocs": len(groups)}


__all__ = ["extract_document", "scan_documents", "build_keyword_index"]
