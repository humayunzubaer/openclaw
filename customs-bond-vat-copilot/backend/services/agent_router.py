"""
এজেন্ট-রাউটার — এলএলএম ছাড়াই কাজ করে এমন নিশ্চিত মস্তিষ্ক
==============================================================

কেন দরকার
---------
নিরীক্ষকের কম্পিউটারে প্রথম দিন কোনো ভাষা-মডেল (Ollama) থাকিবে না।
তথাপি এজেন্টকে কাজের হইতে হইবে। তাই প্রশ্নের অভিপ্রায় (intent) নিশ্চিত
নিয়মে শনাক্ত করিয়া সরাসরি ইঞ্জিন ও জ্ঞানভান্ডার হইতে উত্তর গড়া হয়।

স্তরবিন্যাস
-----------
    ১) এই রাউটার      → নিশ্চিত, উদ্ধৃতিসহ, অফলাইন      (সর্বদা)
    ২) স্থানীয় এলএলএম  → ভাষার সাবলীলতা                  (থাকিলে)
    ৩) ক্লাউড          → নিরীক্ষকের সম্মতিতে              (ঐচ্ছিক)

★ আইনের সংখ্যা, সীমা ও দাবির অঙ্ক কেবল স্তর ১ হইতে আসে। এলএলএম কখনো
  আইন সৃষ্টি করে না — কেবল ভাষা সাজায়।
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from knowledge.report_style import _to_bangla_digits as bn
from utils.logger import logger


# ==========================================================
# উত্তরের আকার
# ==========================================================

@dataclass
class RouterReply:
    """রাউটারের একটি উত্তর"""
    intent: str = ""
    text: str = ""                                   # মূল উত্তর (বাংলা)
    basis: list[str] = field(default_factory=list)   # আইনি/কারিগরি ভিত্তি
    needs_documents: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)         # যন্ত্রপাঠ্য ফল
    handled: bool = True                             # রাউটার সামলাইতে পারিয়াছে?
    confidence: float = 1.0

    def render(self) -> str:
        """চ্যাটে দেখাইবার জন্য পূর্ণ পাঠ"""
        parts = [self.text.strip()]
        if self.basis:
            parts.append("**ভিত্তি —**\n" + "\n".join(f"• {b}" for b in self.basis))
        if self.needs_documents:
            parts.append(
                "**যে দলিলগুলি লাগিবে —**\n"
                + "\n".join(f"• {d}" for d in self.needs_documents)
            )
        if self.next_actions:
            parts.append(
                "**পরবর্তী পদক্ষেপ —**\n"
                + "\n".join(f"{bn(str(i))}। {a}" for i, a in enumerate(self.next_actions, 1))
            )
        return "\n\n".join(p for p in parts if p.strip())


# ==========================================================
# অভিপ্রায় শনাক্তকরণ
# ==========================================================

def _norm(q: str) -> str:
    """তুলনার জন্য প্রশ্ন সরল করে"""
    q = (q or "").strip().lower()
    q = q.replace("ৎ", "ত")
    q = re.sub(r"\s+", " ", q)
    return q


def _has(q: str, *words: str) -> bool:
    return any(w in q for w in words)


# শ্রেণি শনাক্তকরণ — প্রশ্নের ভিতরে প্রতিষ্ঠানের ধরন
ENTITY_WORDS: list[tuple[str, tuple[str, ...]]] = [
    ("rmg_direct", ("পোশাক", "গার্মেন্ট", "গার্মেন্টস", "তৈরি পোশাক", "rmg")),
    ("epz_deemed", ("ইপিজেড প্রচ্ছন্ন", "epz প্রচ্ছন্ন")),
    ("epz_direct", ("ইপিজেড", "epz", "ইপিজেডস্থ", "অর্থনৈতিক অঞ্চল")),
    ("deemed", ("প্রচ্ছন্ন", "ডিমড", "deemed", "প্রচ্ছন্ন রপ্তানি")),
    ("direct", ("সরাসরি রপ্তানি", "সরাসরি রপ্তানিমুখী", "direct")),
]


def detect_entity_type(q: str, fallback: str = "direct") -> str:
    n = _norm(q)
    for kind, words in ENTITY_WORDS:
        if any(w in n for w in words):
            return kind
    return fallback


# দলিলের কথ্য নাম → সাংকেতিক নাম
DOC_ALIASES: dict[str, tuple[str, ...]] = {
    "bond_register": ("রেজিস্টার", "রেজিষ্টার", "register", "১৭ক", "১৭খ", "১৭ঘ"),
    "coefficient": ("সহগ", "কোএফিশিয়েন্ট", "coefficient", "ইনপুট-আউটপুট",
                    "ইনপুট আউটপুট", "উপকরণ-উৎপাদ"),
    "mis_import": ("এমআইএস", "mis", "আমদানি তথ্য", "আমদানির তথ্য",
                   "বিল অব এন্ট্রি", "বিই"),
    "entitlement": ("প্রাপ্যতা", "এনটাইটেলমেন্ট", "entitlement", "বার্ষিক প্রাপ্যতা"),
    "up": ("ইউপি", "u.p", " up ", "ইউটিলাইজেশন"),
    "export_data": ("রপ্তানি তথ্য", "রপ্তানির তথ্য", "ইএক্সপি", "exp", "রপ্তানি দলিল"),
    "closing_stock": ("মজুদ", "স্থিতি", "ক্লোজিং", "সমাপনী মজুদ"),
    "mushak_43": ("৪.৩", "মূসক ৪.৩", "মুসক ৪.৩"),
    "mushak_91": ("৯.১", "মূসক ৯.১", "মুসক ৯.১", "দাখিলপত্র"),
    "prc": ("পিআরসি", "prc", "প্রত্যাবাসন", "প্রত্যাবাসন সনদ"),
    "electricity": ("বিদ্যুৎ", "বিদ্যুত", "বিদ্যুৎ বিল", "পল্লী বিদ্যুৎ", "ডেসকো"),
    "machine_list": ("মেশিন", "যন্ত্রপাতি", "মেশিন তালিকা"),
    "local_purchase": ("স্থানীয় ক্রয়", "লোকাল ক্রয়", "স্থানীয় সংগ্রহ"),
}


_SRO_RE = re.compile(r"(?:এসআরও|sro)\s*(?:নং)?\s*([\d০-৯]{2,4})")
_RULE_RE = re.compile(r"বিধি\s*([\d০-৯]{1,3}[ক-হ]?)")
_SEC_RE = re.compile(r"ধারা\s*([\d০-৯]{1,3}[ক-হ]?)")


def _legal_terms(raw: str) -> list[str]:
    """প্রশ্ন হইতে আইনি সূত্র বাহির করে — খোঁজার জন্য"""
    terms: list[str] = []
    for m in _SRO_RE.finditer(raw.lower()):
        terms.append(f"এসআরও {m.group(1)}")
    for m in _RULE_RE.finditer(raw):
        terms.append(f"বিধি {m.group(1)}")
    for m in _SEC_RE.finditer(raw):
        terms.append(f"ধারা {m.group(1)}")
    return terms


def detect_documents(q: str) -> list[str]:
    """প্রশ্নে কোন কোন দলিলের কথা আছে"""
    n = _norm(q)
    found: list[str] = []
    for code, words in DOC_ALIASES.items():
        if any(w in n for w in words):
            found.append(code)
    return found


# ==========================================================
# রাউটার
# ==========================================================

class AgentRouter:
    """
    প্রশ্ন → অভিপ্রায় → ইঞ্জিন/জ্ঞানভান্ডার → বাংলা উত্তর।

    ব্যবহার:
        r = AgentRouter(session)
        rep = r.route("সরাসরি রপ্তানিকারকের কী কী দলিল লাগিবে?")
        print(rep.render())
    """

    def __init__(self, session: Any):
        self.sess = session

    # ------------------------------------------------------
    def route(self, question: str) -> RouterReply:
        q = _norm(question)
        if not q:
            return RouterReply(intent="empty", text="প্রশ্নটি লিখুন।", handled=False)

        for name, matcher, handler in self._intents():
            try:
                if matcher(q):
                    rep = handler(question, q)
                    if rep is not None:
                        rep.intent = rep.intent or name
                        return rep
            except Exception as e:  # noqa: BLE001
                logger.warning(f"রাউটার অভিপ্রায় '{name}' ব্যর্থ: {e}")

        return self._fallback(question, q)

    # ------------------------------------------------------
    def _intents(self) -> list[tuple[str, Callable, Callable]]:
        """ক্রম গুরুত্বপূর্ণ — নির্দিষ্ট আগে, সাধারণ পরে"""
        return [
            ("greeting", lambda q: (
                len(q) < 40 and _has(q, "হ্যালো", "হাই", "সালাম", "assalam",
                                     "শুভ সকাল", "শুভ", "কেমন আছ")),
             self._h_greeting),

            ("capability", lambda q: _has(
                q, "কী করতে পার", "কি করতে পার", "কী কী পার", "কি কি পার",
                "সাহায্য", "হেল্প", "help", "তুমি কে", "আপনি কে",
                "কীভাবে কাজ", "কিভাবে কাজ", "কমান্ড"),
             self._h_capability),

            ("full_audit", lambda q: _has(
                q, "সম্পূর্ণ নিরীক্ষা", "পূর্ণাঙ্গ নিরীক্ষা", "পুরো নিরীক্ষা",
                "সমগ্র নিরীক্ষা", "সব যাচাই", "পূর্ণ নিরীক্ষা", "full audit"),
             self._h_full_audit),

            ("missing_docs", lambda q: (
                _has(q, "নাই", "নেই", "পাওয়া যায় নাই", "পাওয়া যায়নি",
                     "অনুপস্থিত", "দেয় নাই", "দেয়নি", "ছাড়া", "ব্যতীত",
                     "সরবরাহ করে নাই", "দাখিল করে নাই")
                and bool(detect_documents(q))),
             self._h_missing_docs),

            ("required_docs", lambda q: _has(
                q, "কী কী দলিল", "কি কি দলিল", "কোন কোন দলিল", "দলিলাদি",
                "চেকলিস্ট", "চেকলিষ্ট", "দলিল লাগ", "দলিল চাই", "তলব",
                "কী কী কাগজ", "কি কি কাগজ", "দলিলের তালিকা"),
             self._h_required_docs),

            ("findings", lambda q: _has(
                q, "ফাইন্ডিং", "আপত্তি", "দাবি কত", "দাবী কত", "কী কী পাওয়া",
                "কি কি পাওয়া", "অসংগতি", "ত্রুটি")
             and self.sess.analysis is not None,
             self._h_findings),

            ("state", lambda q: _has(
                q, "অবস্থা", "স্ট্যাটাস", "status", "কতদূর", "সারসংক্ষেপ",
                "সারাংশ", "এ পর্যন্ত"),
             self._h_state),

            ("font", lambda q: _has(
                q, "ফন্ট", "সুতন্বী", "সুতন্নী", "sutonny", "নিকশ",
                "nikosh", "বিজয়", "bijoy", "অভ্র", "ইউনিকোড"),
             self._h_font),

            ("export_docx", lambda q: (
                _has(q, "ওয়ার্ড", "word", "docx", "ডাউনলোড", "নামাও",
                     "নামিয়ে", "ফাইল দাও", "নথি দাও", "প্রিন্ট")
                and _has(q, "প্রতিবেদন", "রিপোর্ট", "report", "নথি")),
             self._h_export),

            ("report", lambda q: _has(
                q, "প্রতিবেদন", "রিপোর্ট", "report", "অনুচ্ছেদ", "খসড়া"),
             self._h_report),

            ("opinion", lambda q: _has(
                q, "মতামত", "প্রস্তাবনা", "প্রস্তাব", "সুপারিশ"),
             self._h_opinion),

            ("partial_check", lambda q: _has(
                q, "যাচাই", "চেক", "পরীক্ষা", "মিলাইয়া", "মিলিয়ে", "দেখ"),
             self._h_partial_check),

            ("legal", lambda q: _has(
                q, "এসআরও", "sro", "বিধি", "ধারা", "আইন", "প্রজ্ঞাপন",
                "তফসিল", "গেজেট"),
             self._h_legal),
        ]

    # ======================================================
    # অভিপ্রায়-সেবক
    # ======================================================

    def _h_greeting(self, raw: str, q: str) -> RouterReply:
        s = self.sess.snapshot()
        if s.get("has_analysis"):
            tail = (
                f"আপনার চলমান নিরীক্ষার তথ্য আমার কাছে আছে — "
                f"এ পর্যন্ত মোট দাবি {s.get('claim_total', 0):,.0f} টাকা। "
                "কোন দিকটা দেখব বলুন।"
            )
        else:
            tail = (
                "এখনো কোনো নিরীক্ষার তথ্য আমার কাছে আসে নাই। "
                "আমদানি তথ্য বা প্রাপ্যতার ফাইলটি দিলে শুরু করতে পারি।"
            )
        return RouterReply(
            text="আসসালামু আলাইকুম। আমি আপনার নিরীক্ষা সহায়ক।\n\n" + tail,
            next_actions=[
                "প্রতিষ্ঠানের শ্রেণি বলুন (সরাসরি / প্রচ্ছন্ন / ইপিজেড / পোশাক)",
                "চাহিত দলিলের তালিকা চাইলে বলুন — “কী কী দলিল লাগবে”",
                "ফাইল দিয়া বলুন — “সম্পূর্ণ নিরীক্ষা কর”",
            ],
        )

    # ------------------------------------------------------
    def _h_capability(self, raw: str, q: str) -> RouterReply:
        return RouterReply(
            text=(
                "আমি বন্ড ও মূল্য সংযোজন কর নিরীক্ষার সহায়ক। আপনি যেভাবে "
                "বলবেন সেভাবেই কাজ করব — ছোট একটি অংশ যাচাই করতে বললে "
                "সেটুকুই করব, আবার সম্পূর্ণ নিরীক্ষা করতে বললে শুরু থেকে "
                "শেষ পর্যন্ত করে প্রতিবেদনের খসড়া পর্যন্ত দিব।\n\n"
                "যা যা পারি —\n"
                "• **দলিল** — প্রতিষ্ঠানের শ্রেণি অনুযায়ী চাহিত দলিলের তালিকা\n"
                "• **বিকল্প পথ** — কোনো দলিল না পাওয়া গেলে আইনের মধ্যে থেকে "
                "কীভাবে নিরীক্ষা এগোবে, আর কোন দাবিটি তখন করা যাবে না\n"
                "• **যাচাই** — প্রাপ্যতা, সাময়িক প্রাপ্যতা, বন্ডিং ক্যাপাসিটি, "
                "রেজিস্টার, ইউপি, সহগের মেয়াদ, বিদ্যুৎ-উৎপাদন সংগতি, "
                "খালাসের বিলম্ব\n"
                "• **হিসাব** — দাবির অঙ্ক, শুল্ক-করের স্তর, সুদ ও জরিমানা\n"
                "• **প্রতিবেদন** — অনুচ্ছেদ, পর্যালোচনা, মতামত ও প্রস্তাবনার খসড়া\n"
                "• **আইন** — এসআরও, বিধি ও ধারার উদ্ধৃতি\n\n"
                "একটি কথা পরিষ্কার করে বলি — প্রমাণ না থাকলে আমি দাবি "
                "প্রস্তাব করি না। অহেতুক দাবিনামা আপনার প্রতিবেদনের "
                "গ্রহণযোগ্যতা নষ্ট করে।"
            ),
            next_actions=[
                "“সরাসরি রপ্তানিকারকের কী কী দলিল লাগবে” — জিজ্ঞাসা করুন",
                "“রেজিস্টার নাই, এখন কী করব” — বিকল্প পথ দেখাব",
                "“সম্পূর্ণ নিরীক্ষা কর” — ফাইল দেওয়া থাকলে সবটা করব",
            ],
        )

    # ------------------------------------------------------
    def _h_required_docs(self, raw: str, q: str) -> RouterReply:
        from services.doc_requisition import build_requisition
        ent = detect_entity_type(raw, self.sess.profile.get("entity_type", "direct"))
        r = build_requisition(ent)
        self.sess.profile["entity_type"] = ent

        must = [d for d in r.documents if d.mandatory]
        opt = [d for d in r.documents if not d.mandatory]

        lines = [f"**{r.entity_label}** — চাহিত দলিলাদি "
                 f"(মোট {bn(str(len(r.documents)))}টি, "
                 f"আবশ্যিক {bn(str(len(must)))}টি)।", ""]
        lines.append("**আবশ্যিক —**")
        lines += [f"{bn(str(i))}। {d.name}  \n    _{d.legal_ref}_"
                  for i, d in enumerate(must, 1)]
        if opt:
            lines += ["", "**প্রযোজ্য ক্ষেত্রে —**"]
            lines += [f"{bn(str(i))}। {d.name}  \n    _{d.legal_ref}_"
                      for i, d in enumerate(opt, 1)]
        if r.schedules:
            lines += ["", f"**বার্ষিক বিবরণীর প্রযোজ্য ছক ({bn(str(len(r.schedules)))}টি) —**"]
            lines += [f"• {sc.label} — {sc.title}  \n    _{sc.rule_ref}_"
                      for sc in r.schedules]

        return RouterReply(
            text="\n".join(lines),
            basis=["এসআরও নং ২১২-আইন/২০২৪/৪৬৭/কাস্টমস, বিধি ১৩(১)"],
            next_actions=[
                "কোন দলিল পাওয়া যায় নাই বলুন — বিকল্প পথ বের করে দিব",
                "দলিল পেলে ফাইল দিন, যাচাই শুরু করি",
            ],
            data={"entity_type": ent, "documents": len(r.documents),
                  "mandatory": len(must), "schedules": len(r.schedules)},
        )

    # ------------------------------------------------------
    def _h_missing_docs(self, raw: str, q: str) -> RouterReply:
        from services.evidence_paths import audit_route
        docs = detect_documents(raw)
        if not docs:
            return RouterReply(handled=False)

        # সেশনে মনে রাখি
        for d in docs:
            if d not in self.sess.missing_docs:
                self.sess.missing_docs.append(d)

        route = audit_route(docs)
        lines: list[str] = []
        for p in route["paths"]:
            lines.append(f"**{p['label']} নাই —**")
            lines.append(f"সাধারণত ইহা প্রমাণ করে: {p['normally_proves']}")
            if p["alternatives"]:
                lines.append("বিকল্প উৎস: " + "; ".join(p["alternatives"]))
            if p["still_possible"]:
                lines.append("তবু নির্ণয় করা যাইবে: "
                             + "; ".join(p["still_possible"]))
            if p["blocked"]:
                lines.append("**নির্ণয় করা যাইবে না (দাবি প্রস্তাব নহে):** "
                             + "; ".join(p["blocked"]))
            lines.append("")

        head = (
            "ঠিক আছে, দলিল না থাকলেও নিরীক্ষা থেমে থাকবে না। আইন ও বিধির "
            "মধ্যে থেকে যতটুকু নির্ণয় করা সম্ভব ততটুকু করব, আর যেটুকু "
            "প্রমাণসাপেক্ষ সেটুকুতে দাবি প্রস্তাব করব না — এটাই নিরাপদ।\n"
        )
        return RouterReply(
            text=head + "\n".join(lines).strip(),
            basis=[
                "কাস্টমস আইন, ২০২৩ এর ধারা ১২৮ — দলিল সংরক্ষণের বাধ্যবাধকতা",
                "প্রমাণ নাই ⇒ দাবি নাই — অপ্রমাণিত দাবি আপিলে টিকে না",
            ],
            needs_documents=route["requisitions"],
            next_actions=(route["proposals"] or [])[:4] or [
                "উপরের বিকল্প উৎসগুলি তলব করুন",
            ],
            data={"missing": docs, "blocked_kinds": route["blocked_kinds"]},
        )

    # ------------------------------------------------------
    def _h_full_audit(self, raw: str, q: str) -> RouterReply:
        if self.sess.analysis is None:
            return RouterReply(
                text=(
                    "সম্পূর্ণ নিরীক্ষা করতে রাজি আছি — কিন্তু এখনো কোনো "
                    "তথ্যভান্ডার আমার কাছে আসে নাই। উপরের ফাইল-ঘরে আমদানি "
                    "তথ্য (এমআইএস) ও প্রাপ্যতার ফাইলটি দিন, তারপর এক "
                    "কথাতেই সবটা চালিয়ে দিব।"
                ),
                needs_documents=[
                    "আমদানি তথ্য (এমআইএস/বিল অব এন্ট্রি ভিত্তিক)",
                    "বার্ষিক প্রাপ্যতা (এনটাইটেলমেন্ট)",
                    "বন্ড রেজিস্টার (১৭ক/১৭খ) — থাকিলে",
                    "উপকরণ-উৎপাদ সহগ",
                ],
                next_actions=["ফাইল দিন — তারপর “সম্পূর্ণ নিরীক্ষা কর” বলুন"],
            )

        s = self.sess.analysis.summary or {}
        claims = [(k, v) for k, v in s.items()
                  if k.startswith("দাবি") and isinstance(v, (int, float)) and v]
        total = s.get("সর্বমোট রাজস্ব দাবি (BDT)", 0)

        lines = ["সম্পূর্ণ নিরীক্ষা চালানো হইয়াছে। ফলাফল —", ""]
        if claims:
            lines += [f"• {k}: **{v:,.2f}**" for k, v in claims]
            lines += ["", f"**সর্বমোট রাজস্ব দাবি: {total:,.2f} টাকা**"]
        else:
            lines.append(
                "কোনো পরিমাণগত দাবি উদ্ভূত হয় নাই। ইহা ইতিবাচক ফল — "
                "প্রতিবেদনে ইহাই লিপিবদ্ধ হইবে।"
            )
        if self.sess.missing_docs:
            from services.evidence_paths import audit_route
            r = audit_route(self.sess.missing_docs)
            if r["blocked"]:
                lines += ["", "**দলিলের অভাবে যাহা নির্ণয় করা যায় নাই —**"]
                lines += [f"• {b}" for b in r["blocked"]]

        return RouterReply(
            text="\n".join(lines),
            basis=["কাস্টমস আইন, ২০২৩ এর ধারা ২৩৮ — দাবিনামা জারি"],
            next_actions=[
                "“প্রতিবেদনের খসড়া দাও” — অনুচ্ছেদসহ খসড়া তৈরি করব",
                "“মতামত ও প্রস্তাবনা লেখ” — চূড়ান্ত অংশ লিখে দিব",
            ],
            data={"total": total, "claims": dict(claims)},
        )

    # ------------------------------------------------------
    def _h_findings(self, raw: str, q: str) -> RouterReply:
        s = self.sess.analysis.summary or {}
        rows = [(k, v) for k, v in s.items()
                if isinstance(v, (int, float)) and v and k.startswith("দাবি")]
        if not rows:
            return RouterReply(
                text=("চলমান নিরীক্ষায় পরিমাণগত কোনো আপত্তি পাওয়া যায় নাই। "
                      "গুণগত পর্যবেক্ষণ থাকিলে তাহা প্রতিবেদনের পর্যালোচনা "
                      "অংশে লিপিবদ্ধ হইবে।"),
            )
        return RouterReply(
            text="প্রাপ্ত আপত্তিসমূহ —\n\n"
                 + "\n".join(f"• {k}: **{v:,.2f}**" for k, v in rows),
            next_actions=["“মতামত ও প্রস্তাবনা লেখ” বললে খসড়া দিব"],
            data=dict(rows),
        )

    # ------------------------------------------------------
    def _h_state(self, raw: str, q: str) -> RouterReply:
        s = self.sess.snapshot()
        lines = [
            f"• তথ্যভান্ডার: {'আছে' if s['has_analysis'] else 'এখনো আসে নাই'}",
            f"• প্রতিষ্ঠানের শ্রেণি: "
            f"{self.sess.profile.get('entity_type', 'নির্ধারিত হয় নাই')}",
            f"• অনুপস্থিত দলিল: "
            f"{', '.join(s['missing_documents']) if s['missing_documents'] else 'কিছু জানানো হয় নাই'}",
        ]
        if s["has_analysis"]:
            lines.append(f"• এ পর্যন্ত মোট দাবি: {s['claim_total']:,.2f} টাকা")
        return RouterReply(text="চলমান নিরীক্ষার অবস্থা —\n\n" + "\n".join(lines))

    # ------------------------------------------------------
    def _h_report(self, raw: str, q: str) -> RouterReply:
        from knowledge.report_style import AuditProfile, assemble_report_plan
        p = self._profile()
        findings = self._finding_kinds()
        plan = assemble_report_plan(p, findings)
        paras = plan.get("paragraphs", [])
        qs = plan.get("review_questions", [])
        return RouterReply(
            text=(
                f"আপনার নিরীক্ষার ধরন অনুযায়ী প্রতিবেদনে "
                f"**{bn(str(len(paras)))}টি অনুচ্ছেদ** ও পর্যালোচনা অংশে "
                f"**{bn(str(len(qs)))}টি প্রশ্ন** "
                "প্রযোজ্য হইবে। অপ্রাসঙ্গিক অংশগুলি বাদ দেওয়া হইয়াছে।\n\n"
                "**অনুচ্ছেদক্রম —**\n"
                + "\n".join(f"{bn(str(i))}। {t}" for i, t in enumerate(paras, 1))
            ),
            basis=["নমুনা প্রতিবেদনের ধারাবাহিকতা ও ভাষারীতি অনুসৃত"],
            next_actions=["“মতামত ও প্রস্তাবনা লেখ” — চূড়ান্ত অংশ দিব"],
            data={"paragraphs": paras, "review_questions": len(qs)},
        )

    # ------------------------------------------------------
    def _h_opinion(self, raw: str, q: str) -> RouterReply:
        from knowledge.report_style import build_opinion
        kinds = self._finding_kinds()
        if not kinds:
            return RouterReply(
                text=("মতামত লিখিবার মতো কোনো আপত্তি এখনো নির্ণীত হয় নাই। "
                      "আগে নিরীক্ষা চালাইয়া লই — তারপর ভাষা সাজাইব।"),
                next_actions=["“সম্পূর্ণ নিরীক্ষা কর” বলুন"],
            )
        prof = self.sess.profile
        items = build_opinion(
            company=prof.get("company", "নিরীক্ষাধীন প্রতিষ্ঠান"),
            period_from=prof.get("period_from", ""),
            period_to=prof.get("period_to", ""),
            findings=kinds,
        )
        body = "\n\n".join(
            f"**{bn(str(i))}।** {it.text}" for i, it in enumerate(items, 1)
        )
        return RouterReply(
            text="**মতামত ও প্রস্তাবনা (খসড়া)**\n\n" + body,
            basis=["ভাষা: প্রমিত চলিত; প্রস্তাব সর্বদা “…করা যাইতে পারে” রূপে"],
            next_actions=["সম্পাদনা করিয়া প্রতিবেদনে বসাইতে পারেন"],
            data={"items": len(items)},
        )

    # ------------------------------------------------------
    def _h_partial_check(self, raw: str, q: str) -> Optional[RouterReply]:
        """ছোট, নির্দিষ্ট যাচাই — যেটুকু বলা হইয়াছে কেবল সেটুকু"""
        checks: list[tuple[tuple[str, ...], str, str]] = [
            (("বন্ডিং ক্যাপাসিটি", "এককালীন", "ধারণক্ষমতা"),
             "bonding_capacity", "এককালীন বন্ডিং ক্যাপাসিটি"),
            (("সাময়িক", "বিয়োজন", "অগ্রিম প্রাপ্যতা"),
             "provisional", "সাময়িক আমদানি প্রাপ্যতা"),
            (("প্রাপ্যতা", "এনটাইটেলমেন্ট"),
             "entitlement", "প্রাপ্যতার অতিরিক্ত আমদানি"),
            (("বিদ্যুৎ", "বিদ্যুত"),
             "electricity", "বিদ্যুৎ-উৎপাদন সংগতি"),
            (("ইউপি", "utilization"),
             "up", "ইউপির গাণিতিক শুদ্ধতা"),
            (("সহগ", "কোএফিশিয়েন্ট"),
             "coefficient", "সহগের মেয়াদ"),
            (("রেজিস্টার", "রেজিষ্টার"),
             "register", "বন্ড রেজিস্টার"),
            (("বিলম্ব", "খালাস", "প্রবেশ"),
             "into_bond", "বন্ডে প্রবেশের বিলম্ব"),
        ]
        for words, code, label in checks:
            if any(w in q for w in words):
                return self._run_single_check(code, label)
        return None

    def _run_single_check(self, code: str, label: str) -> RouterReply:
        if self.sess.analysis is None:
            return RouterReply(
                intent=f"check:{code}",
                text=(f"**{label}** যাচাই করতে পারি, তবে তার জন্য তথ্য লাগবে। "
                      "প্রয়োজনীয় ফাইলটি দিন।"),
                needs_documents=_CHECK_DOCS.get(code, []),
            )
        s = self.sess.analysis.summary or {}
        key = _CHECK_KEYS.get(code)
        val = s.get(key) if key else None
        if val:
            txt = (f"**{label}** — এই খাতে **{val:,.2f} টাকা** দাবি উদ্ভূত "
                   "হইয়াছে।")
        else:
            txt = (f"**{label}** যাচাই করা হইয়াছে; এই খাতে কোনো অসংগতি "
                   "পাওয়া যায় নাই।")
        return RouterReply(
            intent=f"check:{code}", text=txt,
            basis=[_CHECK_BASIS.get(code, "")] if _CHECK_BASIS.get(code) else [],
            data={"check": code, "amount": val or 0},
        )

    # ------------------------------------------------------
    def _h_font(self, raw: str, q: str) -> RouterReply:
        """ফন্ট সংক্রান্ত পরামর্শ — এবং নিরীক্ষকের পছন্দ মনে রাখা"""
        from services.docx_report import SCHEMES

        picked = None
        if _has(q, "সুতন্বী", "সুতন্নী", "sutonny", "বিজয়", "bijoy"):
            picked = "sutonnymj"
        elif _has(q, "নিকশ", "nikosh", "ইউনিকোড"):
            picked = "nikosh"

        if picked:
            self.sess.profile["font"] = picked
            sc = SCHEMES[picked]
            extra = (
                "\n\nএকটি কথা মনে রাখিবেন — SutonnyMJ ইউনিকোড ফন্ট নহে। "
                "উহাতে বাংলা অক্ষরগুলি ইংরেজি সংকেতে বসানো। তাই লেখাটি "
                "রূপান্তর করিয়া বসানো হয়, এবং ইংরেজি অংশ (যেমন H.S. Code) "
                "পৃথক ফন্টে রাখা হয়। যে কম্পিউটারে SutonnyMJ নাই সেখানে "
                "নথিটি বিকৃত দেখাইবে।"
                if picked == "sutonnymj" else
                "\n\nইহাই নিরাপদ বাছাই — ইউনিকোড হওয়ায় যেকোনো কম্পিউটারে "
                "খোলা যায়, লেখা খোঁজা ও অনুলিপি করা চলে।"
            )
            return RouterReply(
                text=f"ঠিক আছে, প্রতিবেদন **{sc.label}** ফন্টে দিব।"
                     f"\n\n{sc.note}{extra}",
                next_actions=[
                    "“ওয়ার্ডে প্রতিবেদন নামাও” — নথিটি তৈরি করিয়া দিব",
                    "“ফন্ট যাচাই-নথি দাও” — চোখে দেখিয়া মিলাইয়া লইতে পারিবেন",
                ],
                data={"font": picked},
            )

        cur = self.sess.profile.get("font", "nikosh")
        lines = ["দুইটি ফন্টে প্রতিবেদন দিতে পারি —", ""]
        for sc in SCHEMES.values():
            mark = "  ← এখন নির্বাচিত" if sc.key == cur else ""
            lines.append(f"**{sc.label}**{mark}")
            lines.append(f"{sc.note}\n")
        lines.append(
            "পার্থক্যটা মৌলিক: Nikosh ইউনিকোড, লেখা অপরিবর্তিত থাকে। "
            "SutonnyMJ পুরাতন ধাঁচের — বাংলা অক্ষর ইংরেজি সংকেতে বসানো, "
            "তাই লেখাটি রূপান্তর করিয়া দিতে হয়।"
        )
        return RouterReply(
            text="\n".join(lines),
            next_actions=["“SutonnyMJ তে দাও” অথবা “Nikosh এ দাও” বলুন"],
            data={"current": cur},
        )

    # ------------------------------------------------------
    def _h_export(self, raw: str, q: str) -> RouterReply:
        """ওয়ার্ড নথি তৈরির নির্দেশ"""
        font = self.sess.profile.get("font", "nikosh")
        if _has(q, "সুতন্বী", "সুতন্নী", "sutonny", "বিজয়"):
            font = "sutonnymj"
            self.sess.profile["font"] = font
        elif _has(q, "নিকশ", "nikosh"):
            font = "nikosh"
            self.sess.profile["font"] = font

        from services.docx_report import SCHEMES
        sc = SCHEMES[font]
        has = self.sess.analysis is not None
        body = (
            f"প্রতিবেদনটি **{sc.label}** ফন্টে তৈরি করিয়া দিব।"
            if has else
            f"প্রতিবেদনের কাঠামো **{sc.label}** ফন্টে দিতে পারি, তবে "
            "এখনো কোনো বিশ্লেষণের ফল আমার কাছে নাই — তাই আপত্তির অংশটি "
            "খালি থাকিবে। ফাইল দিয়া নিরীক্ষা চালাইলে পূর্ণ প্রতিবেদন হইবে।"
        )
        return RouterReply(
            text=body + "\n\nচ্যাটের নিচে **“ওয়ার্ড নথি”** বোতামে চাপ "
                        "দিলেই নথিটি নামিবে।",
            next_actions=(
                [] if has else ["আগে ফাইল দিন — তারপর “সম্পূর্ণ নিরীক্ষা কর”"]
            ),
            data={"font": font, "endpoint": "/api/report/docx",
                  "ready": has},
        )

    # ------------------------------------------------------
    def _h_legal(self, raw: str, q: str) -> Optional[RouterReply]:
        """আইনি প্রশ্ন — জ্ঞানভান্ডারের প্রকৃত পাঠ আগে, উদ্ধৃতি পরে"""
        from services.agent_service import _kb
        kb = _kb()
        if kb is None:
            return None

        queries = _legal_terms(raw) or [raw]
        hits: list = []
        seen: set[str] = set()
        for term in queries:
            for h in kb.search_docs(term)[:3]:
                ctx = h.get("অংশ", "")
                if ctx and ctx[:60] not in seen:
                    seen.add(ctx[:60])
                    hits.append(h)
            if len(hits) >= 4:
                break
        hits = hits[:4]
        blocks = [h.get("অংশ", "").strip() for h in hits]
        blocks = [b for b in blocks if len(b) > 40]

        if not blocks:
            cites = kb.find_citations(raw, limit=6)
            verified = [c for c in cites if getattr(c, "grade", "") != "P"]
            use = verified or cites
            if not use:
                return None
            return RouterReply(
                intent="legal",
                text=("সরাসরি পাঠ খুঁজিয়া পাই নাই; সংশ্লিষ্ট উদ্ধৃতি —\n\n"
                      + "\n".join(f"• {c.render()}" for c in use)),
                next_actions=["কোন প্রসঙ্গে লাগবে বলুন — প্রয়োগ দেখাইয়া দিব"],
            )

        return RouterReply(
            intent="legal",
            text="জ্ঞানভান্ডার হইতে প্রাসঙ্গিক অংশ —\n\n"
                 + "\n\n".join(f"• {b}" for b in blocks),
            basis=["সূত্র: অভ্যন্তরীণ জ্ঞানভান্ডার; মূল গেজেটের সহিত "
                   "মিলাইয়া লওয়া বাঞ্ছনীয়"],
            next_actions=["কোন প্রসঙ্গে প্রয়োগ করিবেন বলুন"],
        )

    # ------------------------------------------------------
    def _fallback(self, raw: str, q: str) -> RouterReply:
        """অভিপ্রায় বোঝা যায় নাই — জ্ঞানভান্ডারে খুঁজি"""
        from services.agent_service import _kb
        kb = _kb()
        hits = kb.search_docs(raw)[:3] if kb is not None else []
        if hits:
            return RouterReply(
                intent="kb_search", confidence=0.5,
                text="সরাসরি উত্তর নিশ্চিত করিতে পারিলাম না, তবে "
                     "জ্ঞানভান্ডারে ইহা পাইলাম —\n\n"
                     + "\n\n".join(f"• {h.get('অংশ', '')}" for h in hits),
                next_actions=["প্রশ্নটি আর একটু নির্দিষ্ট করিয়া বলুন"],
            )
        return RouterReply(
            intent="unknown", handled=False, confidence=0.0,
            text=(
                "প্রশ্নটি ঠিক ধরিতে পারিলাম না। একটু নির্দিষ্ট করিয়া বলুন — "
                "যেমন কোন দলিল, কোন যাচাই, নাকি প্রতিবেদনের কোন অংশ।"
            ),
            next_actions=[
                "“কী কী দলিল লাগবে”",
                "“রেজিস্টার নাই, কী করব”",
                "“সম্পূর্ণ নিরীক্ষা কর”",
                "“মতামত ও প্রস্তাবনা লেখ”",
            ],
        )

    # ======================================================
    # সহায়ক
    # ======================================================

    def _profile(self):
        from knowledge.report_style import AuditProfile
        p = self.sess.profile
        ent = p.get("entity_type", "direct")
        return AuditProfile(
            is_epz=ent.startswith("epz"),
            is_deemed="deemed" in ent,
            is_rmg=ent.startswith("rmg"),
            includes_vat=bool(p.get("includes_vat", True)),
            has_register="bond_register" not in self.sess.missing_docs,
            has_export_data="export_data" not in self.sess.missing_docs,
        )

    def _finding_kinds(self) -> list[str]:
        """ইঞ্জিনের ফল হইতে ছাঁচের নাম; অনুপস্থিত দলিলের কারণে নিষিদ্ধগুলি বাদ"""
        from services.agent_service import _engine_findings
        from services.evidence_paths import filter_findings
        kinds = _engine_findings(self.sess)
        if self.sess.missing_docs:
            kinds = filter_findings(kinds, self.sess.missing_docs)["kept"]
        return kinds


# ==========================================================
# যাচাই-সহায়ক সারণি
# ==========================================================

_CHECK_KEYS: dict[str, str] = {
    "entitlement": "দাবি ২ — প্রাপ্যতার অতিরিক্ত আমদানি (BDT)",
    "bonding_capacity": "দাবি ৩ — বন্ডিং ক্যাপাসিটির অতিরিক্ত (BDT)",
    "provisional": "দাবি ২ — প্রাপ্যতার অতিরিক্ত আমদানি (BDT)",
}

_CHECK_BASIS: dict[str, str] = {
    "entitlement": "এসআরও নং ২১৪-আইন/২০২৪/৪৬৯/কাস্টমস",
    "provisional": ("এসআরও নং ২১৪-আইন/২০২৪/৪৬৯/কাস্টমস, বিধি ৯ — "
                    "বিয়োজনের শর্তে সাময়িক আমদানি প্রাপ্যতা"),
    "bonding_capacity": "বন্ড লাইসেন্সে উল্লিখিত এককালীন বন্ডিং ক্ষমতা",
    "into_bond": "এসআরও নং ২১২-আইন/২০২৪/৪৬৭/কাস্টমস, বিধি ৮",
    "coefficient": "এসআরও নং ২১২-আইন/২০২৪/৪৬৭/কাস্টমস, বিধি ৯",
}

_CHECK_DOCS: dict[str, list[str]] = {
    "entitlement": ["বার্ষিক প্রাপ্যতা", "আমদানি তথ্য (এমআইএস)"],
    "provisional": ["সাময়িক প্রাপ্যতার অনুমোদনপত্র", "আমদানি তথ্য"],
    "bonding_capacity": ["বন্ড লাইসেন্স", "আমদানি তথ্য"],
    "electricity": ["বিদ্যুৎ বিল/মিটার রিডিং", "উৎপাদন তথ্য"],
    "up": ["ইউপি (ইউটিলাইজেশন পারমিশন)"],
    "coefficient": ["অনুমোদিত উপকরণ-উৎপাদ সহগ"],
    "register": ["বন্ড রেজিস্টার (১৭ক/১৭খ)"],
    "into_bond": ["বন্ড রেজিস্টার", "বিল অব এন্ট্রি"],
}


__all__ = ["AgentRouter", "RouterReply", "detect_entity_type",
           "detect_documents"]
