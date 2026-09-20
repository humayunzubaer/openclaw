"""
Learned Rules — শিক্ষণযোগ্য নিয়ম ভান্ডার
==========================================

উদ্দেশ্য:
    নিরীক্ষক চ্যাটে কোনো নিয়ম, ব্যাখ্যা বা সিদ্ধান্ত বলিলে এজেন্ট উহা
    ধরিয়া লইয়া জ্ঞানভান্ডারে সংরক্ষণ করিবে এবং পরবর্তীতে প্রাসঙ্গিক
    পরিস্থিতিতে স্বয়ংক্রিয়ভাবে প্রয়োগ করিবে।

★ গুরুত্বপূর্ণ নকশাগত সিদ্ধান্ত:
    মডেল নিজে পরিবর্তিত হয় না (fine-tuning নহে)। নিয়ম সংরক্ষিত হয়
    কাঠামোবদ্ধ আকারে এবং প্রশ্নের প্রেক্ষাপটে ইনজেক্ট করা হয়।

    ইহার সুবিধা —
      • প্রতিটি নিয়ম দেখা, সম্পাদনা ও মুছিয়া ফেলা যায়
      • কোন নিয়ম কখন কেন প্রয়োগ হইল তাহা ব্যাখ্যা করা যায়
      • ভুল নিয়ম প্রত্যাহার করিলে সঙ্গে সঙ্গে প্রভাব বন্ধ হয়
      • নিরীক্ষা কার্যপত্রে নিয়মের উৎস উদ্ধৃত করা যায়

    fine-tuning এ এই কোনোটিই সম্ভব নহে — তাই ইহাই অধিকতর নিরাপদ।
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from utils.logger import logger


# ==========================================================
# নিয়মের শ্রেণী
# ==========================================================

RULE_SCOPES = {
    "import": "আমদানি বিশ্লেষণ",
    "entitlement": "প্রাপ্যতা নির্ধারণ",
    "capacity": "বন্ডিং ক্যাপাসিটি",
    "assessment": "শুল্কায়ন",
    "consumption": "ভোগ ও উৎপাদন",
    "export": "রপ্তানি",
    "inventory": "মজুত",
    "vat": "মূল্য সংযোজন কর",
    "legal": "আইনি উদ্ধৃতি",
    "report": "প্রতিবেদন প্রণয়ন",
    "general": "সাধারণ",
}

RULE_KINDS = {
    "definition": "সংজ্ঞা",           # "প্রাপ্যতা মানে শীটের পরিমাণ + মজুত"
    "formula": "সূত্র",               # "ক্যাপাসিটি = min(প্রাপ্যতা÷৩, ধারণক্ষমতা)"
    "threshold": "সীমা",              # "সহনসীমা শূন্য"
    "procedure": "পদ্ধতি",            # "রেজিস্টার না পাইলে ফাইন্ডিংস দিবে না"
    "citation": "আইনি উদ্ধৃতি",       # "এইটি বিধি ১২(১) এর আওতায়"
    "exception": "ব্যতিক্রম",         # "মেশিনারিজ বাদ"
    "preference": "পছন্দ",            # "রিপোর্টে সাধু ভাষা ব্যবহার করিবে"
    "correction": "সংশোধন",           # পূর্বের ভুল শোধরানো
}


@dataclass
class LearnedRule:
    """নিরীক্ষক কর্তৃক শেখানো একটি নিয়ম"""
    id: Optional[int] = None
    scope: str = "general"
    kind: str = "procedure"

    # মূল বিষয়বস্তু
    statement: str = ""              # নিরীক্ষকের কথা, হুবহু
    normalized: str = ""             # অনুসন্ধানের জন্য
    summary: str = ""                # সংক্ষিপ্ত রূপ

    # প্রয়োগের সংকেত
    keywords: list[str] = field(default_factory=list)
    applies_when: str = ""           # কখন প্রযোজ্য
    legal_reference: str = ""

    # অবস্থা
    is_active: bool = True
    confidence: float = 1.0          # নিরীক্ষক বলিয়াছেন → পূর্ণ আস্থা
    priority: int = 100              # কম সংখ্যা = অধিক অগ্রাধিকার

    # সম্পর্ক
    supersedes: Optional[int] = None  # কোন নিয়মকে বাতিল করে
    superseded_by: Optional[int] = None

    # নিরীক্ষণ চিহ্ন
    source: str = "chat"             # chat | manual | import
    taught_by: str = ""
    taught_at: str = ""
    times_applied: int = 0
    last_applied: str = ""
    session_ref: str = ""            # কোন অডিট সেশনে শেখানো

    def __post_init__(self):
        if not self.normalized:
            self.normalized = _normalize(self.statement)
        if not self.summary:
            self.summary = self.statement[:150]
        if not self.taught_at:
            self.taught_at = datetime.now().isoformat(timespec="seconds")
        if not self.keywords:
            self.keywords = extract_keywords(self.statement)


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFC", str(text)).lower()
    s = re.sub(r"[^\w\s\u0980-\u09FF]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ==========================================================
# কীওয়ার্ড নিষ্কাশন
# ==========================================================

_STOP = {
    "এই", "এটি", "এটা", "সেই", "তার", "এর", "ও", "এবং", "বা", "কিন্তু",
    "যদি", "তবে", "হবে", "হইবে", "করবে", "করিবে", "করতে", "করিতে",
    "থেকে", "হতে", "হইতে", "জন্য", "সাথে", "সহিত", "মধ্যে", "উপর",
    "না", "নয়", "নহে", "কোনো", "কোন", "সব", "সকল", "আপনি", "আমি",
    "the", "is", "are", "will", "would", "should", "must", "and", "or",
    "for", "with", "from", "this", "that", "not", "you", "please",
}


def extract_keywords(text: str | None, limit: int = 12) -> list[str]:
    """নিয়ম হইতে অনুসন্ধানযোগ্য শব্দ বাহির করো"""
    if not text:
        return []
    words = _normalize(text).split()
    out: list[str] = []
    seen: set[str] = set()
    for w in words:
        if len(w) < 2 or w in _STOP or w.isdigit():
            continue
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= limit:
            break
    return out


# ==========================================================
# নিয়ম শনাক্তকরণ — কথোপকথনে নিয়ম আছে কিনা
# ==========================================================

# নিরীক্ষক নিয়ম শেখাইতেছেন এমন সংকেত
_TEACH_SIGNALS = [
    # বাংলা
    r"মনে\s*রাখ", r"মনে\s*রেখ", r"শিখে?\s*নি", r"যুক্ত\s*কর",
    r"নিয়ম\s*হ", r"নিয়মটি", r"এখন\s*থেকে", r"সবসময়", r"সর্বদা",
    r"প্রতিবার", r"অবশ্যই", r"কখনো\s*না", r"করবেন?\s*না",
    r"হবে\s*না", r"ভুল\s*হয়েছে", r"সংশোধন", r"ঠিক\s*কর",
    r"খেয়াল\s*রাখ", r"লক্ষ্য\s*রাখ", r"বুঝে?\s*নি", r"আয়ত্ত\s*কর",
    r"এভাবে\s*কর", r"এইভাবে", r"পরবর্তীতে", r"ভবিষ্যতে",
    # শর্তসাপেক্ষ নির্দেশ — "না পেলে ... দেবেন না"
    r"না\s*পেলে", r"না\s*পাইলে", r"না\s*থাকলে", r"না\s*থাকিলে",
    r"পেলে\s+", r"হলে\s+.{0,40}(দেবেন|দিবেন|করবেন|করিবেন|হবে|হইবে)",
    r"(দেবেন|দিবেন|করবেন|করিবেন|নেবেন|নিবেন)\s*না",
    r"ক্ষেত্রে\s+", r"যেক্ষেত্রে", r"তাহলে", r"সেক্ষেত্রে",
    r"গণ্য\s*হবে", r"গণ্য\s*হইবে", r"বিবেচিত", r"বিবেচ্য",
    r"প্রযোজ্য", r"বাধ্যতামূলক", r"আবশ্যক", r"বিরত\s*থাক",
    # ইংরেজি
    r"\bremember\b", r"\balways\b", r"\bnever\b", r"\bfrom now on\b",
    r"\bmake sure\b", r"\bnote that\b", r"\bthe rule is\b",
    r"\byou must\b", r"\bdon'?t\b", r"\bcorrect(?:ion)?\b",
]
_TEACH_RE = re.compile("|".join(_TEACH_SIGNALS), flags=re.IGNORECASE)

# পরিধি অনুমানের সংকেত
_SCOPE_HINTS = {
    "capacity": ["ক্যাপাসিটি", "ধারণক্ষমতা", "মজুত", "ওয়্যারহাউস",
                 "এককালীন", "capacity", "warehouse"],
    "entitlement": ["প্রাপ্যতা", "entitlement", "প্রদত্ত", "প্রস্তাবিত"],
    "assessment": ["শুল্কায়ন", "দাবি", "দাবিনামা", "শুল্ক", "কর",
                   "মূসক", "ভ্যাট", "assessment", "duty"],
    "import": ["আমদানি", "বিল অব এন্ট্রি", "এইচএস", "import", "mis"],
    "consumption": ["ভোগ", "খরচ", "উৎপাদন", "consumption", "yield"],
    "export": ["রপ্তানি", "export", "ইউপি", "exp"],
    "inventory": ["মজুদ", "স্টক", "জের", "inventory", "stock"],
    "vat": ["মূসক", "ভ্যাট", "vat", "৯.১", "মূসক-৯.১"],
    "legal": ["বিধি", "ধারা", "এসআরও", "আইন", "উদ্ধৃতি", "sro", "rule"],
    "report": ["প্রতিবেদন", "রিপোর্ট", "কার্যপত্র", "ফন্ট", "report"],
}

_KIND_HINTS = {
    "formula": ["সূত্র", "=", "÷", "গুণ", "ভাগ", "যোগ", "বিয়োগ",
                "formula", "min(", "max("],
    "threshold": ["সীমা", "শতাংশ", "%", "সহনসীমা", "সর্বোচ্চ", "সর্বনিম্ন",
                  "threshold", "limit"],
    "definition": ["মানে", "সংজ্ঞা", "বলিতে", "বুঝায়", "অর্থ",
                   "means", "definition"],
    "exception": ["ব্যতীত", "বাদে", "ছাড়া", "ব্যতিক্রম", "except", "exclude"],
    "citation": ["বিধি", "ধারা", "এসআরও", "sro", "section", "rule"],
    "correction": ["ভুল", "সংশোধন", "ঠিক নয়", "wrong", "correct", "mistake"],
    "preference": ["পছন্দ", "ভাষা", "ফন্ট", "শৈলী", "prefer", "style"],
}


@dataclass
class RuleDetection:
    """কথোপকথনে নিয়ম শনাক্তকরণের ফলাফল"""
    is_rule: bool = False
    confidence: float = 0.0
    scope: str = "general"
    kind: str = "procedure"
    signals: list[str] = field(default_factory=list)
    suggested_summary: str = ""


def detect_rule(message: str | None) -> RuleDetection:
    """
    নিরীক্ষকের বার্তায় শেখানোর মতো নিয়ম আছে কিনা নির্ণয় করো।

    ★ এজেন্ট নিজে সিদ্ধান্ত নেয় না — শনাক্ত করিয়া নিরীক্ষককে
      নিশ্চিতকরণের জন্য জিজ্ঞাসা করে।
    """
    d = RuleDetection()
    if not message or len(message.strip()) < 10:
        return d

    text = str(message)
    low = text.lower()

    # --- শেখানোর সংকেত ---
    signals = [m.group(0) for m in _TEACH_RE.finditer(text)]
    if signals:
        d.signals = signals[:5]
        d.confidence += min(0.65, 0.35 * len(signals))

    # --- বাক্যের দৈর্ঘ্য ও গঠন ---
    if 20 <= len(text) <= 1200:
        d.confidence += 0.1

    # --- পরিধি অনুমান ---
    best_scope, best_hits = "general", 0
    for scope, hints in _SCOPE_HINTS.items():
        hits = sum(1 for h in hints if h in low or h in text)
        if hits > best_hits:
            best_scope, best_hits = scope, hits
    d.scope = best_scope
    if best_hits:
        d.confidence += min(0.2, 0.07 * best_hits)

    # --- ধরন অনুমান ---
    best_kind, best_k = "procedure", 0
    for kind, hints in _KIND_HINTS.items():
        hits = sum(1 for h in hints if h in low or h in text)
        if hits > best_k:
            best_kind, best_k = kind, hits
    # সূত্র, সীমা, সংজ্ঞা, ব্যতিক্রম — নিজেই শক্ত সংকেত
    if best_kind in ("formula", "threshold", "definition",
                     "exception", "correction", "citation"):
        d.confidence += 0.25

    d.kind = best_kind
    d.confidence = min(1.0, d.confidence)
    d.is_rule = d.confidence >= 0.40
    d.suggested_summary = _summarize(text)
    return d


def _summarize(text: str, limit: int = 160) -> str:
    """নিয়মের সংক্ষিপ্ত রূপ — প্রথম অর্থপূর্ণ বাক্য"""
    s = re.sub(r"\s+", " ", str(text)).strip()
    for sep in ("।", ".", "\n"):
        if sep in s:
            first = s.split(sep)[0].strip()
            if len(first) >= 20:
                return (first + sep)[:limit]
    return s[:limit]


# ==========================================================
# ভান্ডার (SQLite)
# ==========================================================

class LearnedRuleStore:
    """
    শেখা নিয়মের স্থায়ী ভান্ডার।

    সম্পূর্ণ অফলাইন — SQLite ফাইলে সংরক্ষিত।
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------
    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS learned_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL DEFAULT 'general',
                    kind TEXT NOT NULL DEFAULT 'procedure',
                    statement TEXT NOT NULL,
                    normalized TEXT,
                    summary TEXT,
                    keywords TEXT,
                    applies_when TEXT,
                    legal_reference TEXT,
                    is_active INTEGER DEFAULT 1,
                    confidence REAL DEFAULT 1.0,
                    priority INTEGER DEFAULT 100,
                    supersedes INTEGER,
                    superseded_by INTEGER,
                    source TEXT DEFAULT 'chat',
                    taught_by TEXT,
                    taught_at TEXT,
                    times_applied INTEGER DEFAULT 0,
                    last_applied TEXT,
                    session_ref TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS ix_rules_scope ON learned_rules(scope)")
            c.execute("CREATE INDEX IF NOT EXISTS ix_rules_active ON learned_rules(is_active)")
            # পূর্ণপাঠ অনুসন্ধান
            c.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS rules_fts
                USING fts5(statement, summary, keywords, content='')
            """)

    # ------------------------------------------------------
    def add(self, rule: LearnedRule) -> int:
        """নূতন নিয়ম সংরক্ষণ করো"""
        with self._conn() as c:
            cur = c.execute("""
                INSERT INTO learned_rules
                (scope, kind, statement, normalized, summary, keywords,
                 applies_when, legal_reference, is_active, confidence, priority,
                 supersedes, source, taught_by, taught_at, session_ref)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                rule.scope, rule.kind, rule.statement, rule.normalized,
                rule.summary, json.dumps(rule.keywords, ensure_ascii=False),
                rule.applies_when, rule.legal_reference,
                1 if rule.is_active else 0, rule.confidence, rule.priority,
                rule.supersedes, rule.source, rule.taught_by,
                rule.taught_at, rule.session_ref,
            ))
            rid = cur.lastrowid

            # FTS সূচিতে যোগ
            c.execute(
                "INSERT INTO rules_fts(rowid, statement, summary, keywords) "
                "VALUES (?,?,?,?)",
                (rid, rule.statement, rule.summary, " ".join(rule.keywords)),
            )

            # পুরাতন নিয়ম বাতিল করিলে
            if rule.supersedes:
                c.execute(
                    "UPDATE learned_rules SET is_active=0, superseded_by=? "
                    "WHERE id=?", (rid, rule.supersedes),
                )
        logger.success(
            f"নূতন নিয়ম শেখা হইল #{rid} [{RULE_SCOPES.get(rule.scope, rule.scope)}] "
            f"— {rule.summary[:60]}"
        )
        return rid

    # ------------------------------------------------------
    def get(self, rule_id: int) -> Optional[LearnedRule]:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM learned_rules WHERE id=?", (rule_id,)
            ).fetchone()
        return self._to_rule(row) if row else None

    # ------------------------------------------------------
    def list_rules(
        self, scope: str | None = None, active_only: bool = True,
        limit: int = 500,
    ) -> list[LearnedRule]:
        q = "SELECT * FROM learned_rules WHERE 1=1"
        p: list[Any] = []
        if active_only:
            q += " AND is_active=1"
        if scope:
            q += " AND scope=?"
            p.append(scope)
        q += " ORDER BY priority ASC, id DESC LIMIT ?"
        p.append(limit)
        with self._conn() as c:
            rows = c.execute(q, p).fetchall()
        return [self._to_rule(r) for r in rows]

    # ------------------------------------------------------
    def search(self, query: str, limit: int = 10) -> list[LearnedRule]:
        """প্রশ্নের সহিত প্রাসঙ্গিক নিয়ম খুঁজিয়া বাহির করো"""
        if not query:
            return []
        terms = extract_keywords(query, limit=8)
        if not terms:
            return []

        # FTS চেষ্টা
        try:
            fts_q = " OR ".join(f'"{t}"' for t in terms)
            with self._conn() as c:
                rows = c.execute("""
                    SELECT r.* FROM rules_fts f
                    JOIN learned_rules r ON r.id = f.rowid
                    WHERE rules_fts MATCH ? AND r.is_active=1
                    ORDER BY rank LIMIT ?
                """, (fts_q, limit)).fetchall()
            if rows:
                return [self._to_rule(r) for r in rows]
        except sqlite3.Error:
            pass

        # ফলব্যাক — কীওয়ার্ড মিল
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM learned_rules WHERE is_active=1"
            ).fetchall()
        scored: list[tuple[int, sqlite3.Row]] = []
        for r in rows:
            kws = set(json.loads(r["keywords"] or "[]"))
            norm = r["normalized"] or ""
            score = sum(1 for t in terms if t in kws) * 2
            score += sum(1 for t in terms if t in norm)
            if score:
                scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return [self._to_rule(r) for _, r in scored[:limit]]

    # ------------------------------------------------------
    def deactivate(self, rule_id: int, reason: str = "") -> bool:
        with self._conn() as c:
            c.execute(
                "UPDATE learned_rules SET is_active=0, applies_when=? WHERE id=?",
                (f"প্রত্যাহৃত: {reason}" if reason else "প্রত্যাহৃত", rule_id),
            )
        logger.info(f"নিয়ম #{rule_id} প্রত্যাহার করা হইল")
        return True

    def update(self, rule_id: int, **fields) -> bool:
        allowed = {
            "scope", "kind", "statement", "summary", "applies_when",
            "legal_reference", "is_active", "priority", "confidence",
        }
        sets, vals = [], []
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k}=?")
                vals.append(1 if (k == "is_active" and v is True)
                            else (0 if k == "is_active" and v is False else v))
        if not sets:
            return False
        vals.append(rule_id)
        with self._conn() as c:
            c.execute(
                f"UPDATE learned_rules SET {', '.join(sets)} WHERE id=?", vals
            )
        return True

    def mark_applied(self, rule_ids: list[int]):
        """কোন নিয়ম প্রয়োগ হইল তাহা লিপিবদ্ধ করো"""
        if not rule_ids:
            return
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            c.executemany(
                "UPDATE learned_rules SET times_applied = times_applied + 1, "
                "last_applied=? WHERE id=?",
                [(now, i) for i in rule_ids],
            )

    # ------------------------------------------------------
    def stats(self) -> dict:
        with self._conn() as c:
            total = c.execute(
                "SELECT COUNT(*) FROM learned_rules"
            ).fetchone()[0]
            active = c.execute(
                "SELECT COUNT(*) FROM learned_rules WHERE is_active=1"
            ).fetchone()[0]
            by_scope = c.execute(
                "SELECT scope, COUNT(*) c FROM learned_rules "
                "WHERE is_active=1 GROUP BY scope"
            ).fetchall()
            most = c.execute(
                "SELECT summary, times_applied FROM learned_rules "
                "WHERE is_active=1 ORDER BY times_applied DESC LIMIT 5"
            ).fetchall()
        return {
            "মোট নিয়ম": total,
            "সক্রিয় নিয়ম": active,
            "প্রত্যাহৃত": total - active,
            "পরিধি অনুযায়ী": {
                RULE_SCOPES.get(r["scope"], r["scope"]): r["c"] for r in by_scope
            },
            "সর্বাধিক প্রযুক্ত": [
                {"নিয়ম": r["summary"][:60], "বার": r["times_applied"]}
                for r in most
            ],
        }

    # ------------------------------------------------------
    def export_rules(self, out_path: str | Path) -> Path:
        """সব নিয়ম JSON আকারে রপ্তানি — ব্যাকআপ ও স্থানান্তরের জন্য"""
        out = Path(out_path)
        rules = [asdict(r) for r in self.list_rules(active_only=False)]
        out.write_text(
            json.dumps({
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "count": len(rules), "rules": rules,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.success(f"{len(rules)}টি নিয়ম রপ্তানি হইল: {out}")
        return out

    def import_rules(self, in_path: str | Path) -> int:
        """JSON হইতে নিয়ম আমদানি"""
        data = json.loads(Path(in_path).read_text(encoding="utf-8"))
        n = 0
        for d in data.get("rules", []):
            d.pop("id", None)
            d["keywords"] = d.get("keywords") or []
            self.add(LearnedRule(**{
                k: v for k, v in d.items()
                if k in LearnedRule.__dataclass_fields__
            }))
            n += 1
        logger.success(f"{n}টি নিয়ম আমদানি হইল")
        return n

    # ------------------------------------------------------
    @staticmethod
    def _to_rule(row: sqlite3.Row) -> LearnedRule:
        return LearnedRule(
            id=row["id"], scope=row["scope"], kind=row["kind"],
            statement=row["statement"], normalized=row["normalized"] or "",
            summary=row["summary"] or "",
            keywords=json.loads(row["keywords"] or "[]"),
            applies_when=row["applies_when"] or "",
            legal_reference=row["legal_reference"] or "",
            is_active=bool(row["is_active"]),
            confidence=row["confidence"], priority=row["priority"],
            supersedes=row["supersedes"], superseded_by=row["superseded_by"],
            source=row["source"] or "chat", taught_by=row["taught_by"] or "",
            taught_at=row["taught_at"] or "",
            times_applied=row["times_applied"] or 0,
            last_applied=row["last_applied"] or "",
            session_ref=row["session_ref"] or "",
        )


# ==========================================================
# প্রেক্ষাপটে নিয়ম প্রয়োগ
# ==========================================================

def build_rule_context(
    store: LearnedRuleStore,
    query: str,
    scope: str | None = None,
    max_rules: int = 12,
) -> tuple[str, list[int]]:
    """
    ★ প্রশ্নের সহিত প্রাসঙ্গিক শেখা নিয়মসমূহ প্রেক্ষাপট আকারে প্রস্তুত করো।

    ফেরত: (প্রেক্ষাপট লেখা, প্রযুক্ত নিয়মের আইডি তালিকা)
    """
    relevant = store.search(query, limit=max_rules)

    # নির্দিষ্ট পরিধির উচ্চ-অগ্রাধিকার নিয়মও যোগ করো
    if scope:
        for r in store.list_rules(scope=scope, limit=max_rules):
            if r.id not in {x.id for x in relevant}:
                relevant.append(r)

    if not relevant:
        return "", []

    relevant.sort(key=lambda r: (r.priority, -(r.confidence or 0)))
    relevant = relevant[:max_rules]

    lines = [
        "নিরীক্ষক কর্তৃক পূর্বে শেখানো নিয়মাবলি "
        "(ইহা অবশ্যই অনুসরণ করিতে হইবে):",
        "",
    ]
    for r in relevant:
        tag = RULE_SCOPES.get(r.scope, r.scope)
        kind = RULE_KINDS.get(r.kind, r.kind)
        lines.append(f"[নিয়ম #{r.id} | {tag} | {kind}]")
        lines.append(r.statement.strip())
        if r.legal_reference:
            lines.append(f"আইনি ভিত্তি: {r.legal_reference}")
        lines.append("")

    return "\n".join(lines), [r.id for r in relevant if r.id]


__all__ = [
    "LearnedRule", "LearnedRuleStore", "RuleDetection", "detect_rule",
    "build_rule_context", "extract_keywords",
    "RULE_SCOPES", "RULE_KINDS",
]
