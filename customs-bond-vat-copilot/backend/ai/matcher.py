"""
Matching Engine — কাঁচামালের নাম ও ক্লাস্টার মিলকরণ
=====================================================

বাস্তব সমস্যা:
  প্রাপ্যতা শীটে লেখা : "Woven Fabrics of Cotton, Unbleached"
  আমদানি বিলে লেখা   : "Grey Cotton Fabric"
  → একই পণ্য, ভিন্ন নাম।

সমাধান — চার স্তরের মিলকরণ:
  স্তর ১ : HS কোড (সবচেয়ে নির্ভরযোগ্য)
  স্তর ২ : বাণিজ্যিক নাম অভিধান (শেখা জ্ঞান)
  স্তর ৩ : Fuzzy String Matching (বানান ভিন্নতা)
  স্তর ৪ : ক্লাস্টার (একই গোষ্ঠীর পণ্য)
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional, Iterable

# ---- Fuzzy Matching (rapidfuzz থাকলে সেটি, নাহলে difflib) ----
try:
    from rapidfuzz import fuzz as _fuzz

    def _ratio(a: str, b: str) -> float:
        return _fuzz.token_set_ratio(a, b) / 100.0

    def _partial(a: str, b: str) -> float:
        return _fuzz.partial_ratio(a, b) / 100.0

    HAS_RAPIDFUZZ = True
except ImportError:
    from difflib import SequenceMatcher

    def _ratio(a: str, b: str) -> float:
        """token_set_ratio এর সরল বিকল্প"""
        ta, tb = set(a.split()), set(b.split())
        if not ta or not tb:
            return 0.0
        inter = ta & tb
        # সাধারণ টোকেন + অবশিষ্টাংশের মিল
        rest_a = " ".join(sorted(ta - inter))
        rest_b = " ".join(sorted(tb - inter))
        common = " ".join(sorted(inter))
        s1 = SequenceMatcher(None, common, (common + " " + rest_a).strip()).ratio()
        s2 = SequenceMatcher(None, common, (common + " " + rest_b).strip()).ratio()
        s3 = SequenceMatcher(None, a, b).ratio()
        return max(s1, s2, s3)

    def _partial(a: str, b: str) -> float:
        short, long_ = (a, b) if len(a) <= len(b) else (b, a)
        if not short:
            return 0.0
        best = 0.0
        step = max(1, len(short) // 4)
        for i in range(0, max(1, len(long_) - len(short) + 1), step):
            best = max(best, SequenceMatcher(None, short, long_[i:i + len(short)]).ratio())
        return best

    HAS_RAPIDFUZZ = False


# ==========================================================
# শব্দ পরিষ্কারকরণ
# ==========================================================

# অর্থহীন শব্দ — মিলকরণে বাদ দেওয়া হয়
STOPWORDS = {
    "of", "the", "and", "or", "for", "with", "in", "to", "a", "an",
    "other", "others", "etc", "misc", "miscellaneous", "assorted",
    "quality", "grade", "type", "kind", "item", "items", "goods",
    "material", "materials", "raw", "various", "different",
    "including", "excluding", "not", "nes", "n.e.s",
    "এবং", "ও", "এর", "জন্য", "অন্যান্য", "ইত্যাদি",
}

# সমার্থক শব্দ — একই অর্থ, ভিন্ন লেখা
SYNONYM_TOKENS: dict[str, str] = {
    # তন্তু / সুতা
    "poly": "polyester", "pe": "polyester", "pet": "polyester",
    "pp": "polypropylene", "pa": "polyamide", "nylon": "polyamide",
    "ctn": "cotton", "cot": "cotton", "cvc": "cotton",
    "visc": "viscose", "rayon": "viscose",
    "spdx": "spandex", "lycra": "spandex", "elastane": "spandex",
    "acrylic": "acrylic",
    # কাপড়
    "fab": "fabric", "fabrics": "fabric", "cloth": "fabric",
    "textile": "fabric", "woven": "woven", "knit": "knitted",
    "knitted": "knitted", "grey": "unbleached", "gray": "unbleached",
    "greige": "unbleached",
    # সুতা
    "yarns": "yarn", "thread": "thread", "threads": "thread",
    "sewing": "sewing", "twisted": "twisted", "textured": "textured",
    "dty": "textured", "fdy": "filament", "poy": "filament",
    # আনুষঙ্গিক
    "btn": "button", "buttons": "button",
    "zip": "zipper", "zippers": "zipper", "slider": "zipper",
    "lbl": "label", "labels": "label", "tag": "label", "tags": "label",
    "elstc": "elastic", "elastics": "elastic",
    "intrlng": "interlining", "interlinning": "interlining",
    "ctn box": "carton", "cartons": "carton", "box": "carton",
    "boxes": "carton", "corrugated": "carton",
    "poly bag": "polybag", "polybag": "polybag", "pbag": "polybag",
    "hanger": "hanger", "hangers": "hanger",
    "adhesive": "adhesive", "gum": "adhesive", "glue": "adhesive",
    "tape": "tape", "tapes": "tape",
    # রাসায়নিক
    "chem": "chemical", "chemicals": "chemical",
    "dye": "dyes", "dyestuff": "dyes", "colour": "dyes", "color": "dyes",
    "aux": "auxiliary", "auxiliaries": "auxiliary",
    # কাগজ
    "papr": "paper", "papers": "paper", "kraft": "paper",
    # প্লাস্টিক
    "plstc": "plastic", "plastics": "plastic", "pvc": "plastic",
    # প্রক্রিয়া
    "bleach": "bleached", "dyed": "dyed", "printed": "printed",
    "finish": "finished", "finished": "finished",
    "unbleach": "unbleached", "raw": "unbleached",
    # পরিমাপ
    "filament": "filament", "staple": "staple", "spun": "spun",
}


def normalize(text: str | None) -> str:
    """
    মিলকরণের জন্য নাম স্বাভাবিকীকরণ।
    "Woven Fabrics of Cotton, Unbleached" → "cotton fabric unbleached woven"
    """
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text)).lower()

    # ব্র্যাকেটের ভেতরের অংশ রাখো কিন্তু বিরামচিহ্ন সরাও
    s = re.sub(r"[^\w\s\u0980-\u09FF]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    tokens: list[str] = []
    for tok in s.split():
        # খাঁটি সংখ্যা বাদ (যেমন GSM মান)
        if tok.isdigit():
            continue
        if tok in STOPWORDS:
            continue
        tok = SYNONYM_TOKENS.get(tok, tok)
        # বহুবচন → একবচন (সরল নিয়ম)
        if len(tok) > 4 and tok.endswith("s") and not tok.endswith("ss"):
            singular = tok[:-1]
            tok = SYNONYM_TOKENS.get(singular, singular)
        tokens.append(tok)

    # সাজানো — শব্দক্রম নির্বিশেষে মিল
    return " ".join(sorted(set(tokens)))


# ==========================================================
# ক্লাস্টার নির্ধারণ
# ==========================================================

@dataclass
class ClusterRule:
    """একটি ক্লাস্টারের সংজ্ঞা"""
    code: str
    name_bn: str
    name_en: str
    hs_prefixes: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    material_type: str = "raw_material"
    default_unit: str = ""


# বাংলাদেশের পোশাক ও বস্ত্র শিল্পের প্রধান ক্লাস্টার
DEFAULT_CLUSTERS: list[ClusterRule] = [
    ClusterRule("FAB-WOV", "বোনা কাপড়", "Woven Fabric",
                ("52", "5407", "5408", "5512", "5513", "5514", "5515", "5516", "5801", "5802"),
                ("woven", "fabric", "poplin", "twill", "denim", "canvas"), default_unit="YDS"),
    ClusterRule("FAB-KNT", "নিট কাপড়", "Knitted Fabric",
                ("6001", "6002", "6003", "6004", "6005", "6006"),
                ("knitted", "jersey", "rib", "interlock", "fleece"), default_unit="KG"),
    ClusterRule("YRN", "সুতা", "Yarn",
                ("5205", "5206", "5207", "5402", "5403", "5404", "5509", "5510", "5511"),
                ("yarn", "filament", "spun", "textured"), default_unit="KG"),
    ClusterRule("THR", "সেলাই সুতা", "Sewing Thread",
                ("5204", "5401", "5508"),
                ("sewing", "thread"), default_unit="KG"),
    ClusterRule("ACC-BTN", "বোতাম", "Button",
                ("9606",), ("button", "snap")),
    ClusterRule("ACC-ZIP", "চেইন", "Zipper",
                ("9607",), ("zipper", "slider")),
    ClusterRule("ACC-LBL", "লেবেল ও ট্যাগ", "Label & Tag",
                ("5807", "4821"), ("label", "tag", "hangtag", "sticker")),
    ClusterRule("ACC-ELS", "ইলাস্টিক ও টেপ", "Elastic & Narrow Fabric",
                ("5806", "5808"), ("elastic", "narrow", "tape", "webbing")),
    ClusterRule("ACC-INT", "ইন্টারলাইনিং", "Interlining",
                ("5903", "5906", "5907", "5602", "5603"),
                ("interlining", "fusible", "nonwoven")),
    ClusterRule("PKG-CTN", "কার্টন", "Carton & Paper Packing",
                ("4819", "4802", "4805", "4808", "4810"),
                ("carton", "box", "paper", "kraft"), material_type="packing_material"),
    ClusterRule("PKG-POL", "পলি ব্যাগ ও প্লাস্টিক", "Poly Bag & Plastic Packing",
                ("3920", "3921", "3923", "3919"),
                ("polybag", "poly", "plastic", "adhesive", "tape"),
                material_type="packing_material"),
    ClusterRule("PKG-HNG", "হ্যাঙ্গার", "Hanger & Plastic Accessories",
                ("3926",), ("hanger", "clip", "collar"), material_type="packing_material"),
    ClusterRule("CHM-DYE", "রং ও ডাই", "Dyes & Colours",
                ("3204", "3205", "3206", "3207"), ("dyes", "pigment", "colour")),
    ClusterRule("CHM-AUX", "রাসায়নিক সহায়ক", "Chemical Auxiliaries",
                ("3402", "3403", "3809", "3824", "2915", "2917"),
                ("chemical", "auxiliary", "softener", "detergent", "enzyme")),
]


# ==========================================================
# মেশিনারিজ শনাক্তকরণ
# ==========================================================
#
# নিয়ম: প্রাপ্যতা শীটে না থাকা পণ্য = অননুমোদিত আমদানি।
#        তবে মেশিনারিজ ও যন্ত্রাংশ এই নিয়মের বাইরে —
#        কারণ মূলধনী যন্ত্রপাতি ভিন্ন অনুমোদন প্রক্রিয়ায় আমদানি হয়।

MACHINERY_HS_CHAPTERS: tuple[str, ...] = (
    "82",   # হাতিয়ার, যন্ত্রপাতি, ছুরি-কাঁচি
    "84",   # যন্ত্রপাতি ও যান্ত্রিক সরঞ্জাম
    "85",   # বৈদ্যুতিক যন্ত্রপাতি ও সরঞ্জাম
    "86",   # রেল সরঞ্জাম
    "87",   # যানবাহন
    "90",   # পরিমাপক ও পরীক্ষণ যন্ত্র
)

MACHINERY_KEYWORDS: tuple[str, ...] = (
    "machine", "machinery", "machineries", "equipment", "apparatus",
    "spare", "spares", "part", "parts", "component", "accessory of machine",
    "motor", "generator", "compressor", "boiler", "pump", "transformer",
    "cutter", "sewing machine", "knitting machine", "dyeing machine",
    "needle", "bobbin", "spindle", "gear", "bearing", "belt drive",
    "controller", "sensor", "panel", "switch", "cable", "wire",
    "মেশিন", "যন্ত্র", "যন্ত্রপাতি", "যন্ত্রাংশ", "খুচরা যন্ত্রাংশ",
)


def is_machinery(item_name: str | None, hs_code: str | None = None) -> tuple[bool, str]:
    """
    পণ্যটি মেশিনারিজ/যন্ত্রাংশ কিনা নির্ধারণ করো।

    ফেরত দেয়: (মেশিনারিজ কিনা, কারণ)
    """
    # --- HS অধ্যায় দিয়ে (সবচেয়ে নির্ভরযোগ্য) ---
    if hs_code:
        digits = re.sub(r"\D", "", str(hs_code))
        if len(digits) >= 2 and digits[:2] in MACHINERY_HS_CHAPTERS:
            return True, f"HS অধ্যায় {digits[:2]} — মূলধনী যন্ত্রপাতি/যন্ত্রাংশ"

    # --- নাম দিয়ে ---
    if item_name:
        norm = normalize(item_name)
        tokens = set(norm.split())
        for kw in MACHINERY_KEYWORDS:
            if " " in kw:
                if kw in norm:
                    return True, f"পণ্যের নামে '{kw}' উল্লেখ — যন্ত্রপাতি হিসেবে বিবেচ্য"
            elif kw in tokens:
                return True, f"পণ্যের নামে '{kw}' উল্লেখ — যন্ত্রপাতি হিসেবে বিবেচ্য"

    return False, ""


def detect_cluster(
    item_name: str | None,
    hs_code: str | None = None,
    clusters: list[ClusterRule] = None,
) -> tuple[Optional[str], float]:
    """
    পণ্যের ক্লাস্টার নির্ধারণ করো।
    ফেরত দেয়: (cluster_code, confidence)
    """
    clusters = clusters or DEFAULT_CLUSTERS

    # --- HS কোড দিয়ে (সবচেয়ে নির্ভরযোগ্য) ---
    if hs_code:
        digits = re.sub(r"\D", "", str(hs_code))
        if digits:
            best_prefix_len, best_code = 0, None
            for c in clusters:
                for pre in c.hs_prefixes:
                    if digits.startswith(pre) and len(pre) > best_prefix_len:
                        best_prefix_len, best_code = len(pre), c.code
            if best_code:
                # ৪ সংখ্যার মিল = উচ্চ আস্থা, ২ সংখ্যার = মাঝারি
                conf = 0.95 if best_prefix_len >= 4 else 0.75
                return best_code, conf

    # --- কীওয়ার্ড দিয়ে ---
    if item_name:
        norm = normalize(item_name)
        tokens = set(norm.split())
        best_code, best_hits = None, 0
        for c in clusters:
            hits = sum(1 for kw in c.keywords if kw in tokens)
            if hits > best_hits:
                best_hits, best_code = hits, c.code
        if best_code:
            return best_code, min(0.5 + 0.15 * best_hits, 0.85)

    return None, 0.0


# ==========================================================
# মিলকরণ ফলাফল
# ==========================================================

@dataclass
class MatchResult:
    """একটি মিলকরণের ফলাফল — Explainable"""
    matched: bool = False
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    target_hs: Optional[str] = None
    score: float = 0.0
    method: str = "none"
    # hs_exact | hs_heading | dictionary | fuzzy_name | cluster | none
    explanation: str = ""
    alternatives: list[dict] = field(default_factory=list)

    @property
    def confidence_label(self) -> str:
        if self.score >= 0.90:
            return "উচ্চ"
        if self.score >= 0.70:
            return "মাঝারি"
        if self.score > 0:
            return "নিম্ন"
        return "নেই"


@dataclass
class MatchCandidate:
    """
    মিলকরণের লক্ষ্যবস্তু — একটি প্রাপ্যতা-একক।

    ইহা একটিমাত্র কাঁচামাল হইতে পারে, অথবা প্রাপ্যতা শীটে উল্লিখিত
    একটি ক্লাস্টার — যাহার অধীনে একাধিক এইচ.এস কোড ও নাম থাকে।
    """
    id: int
    name: str
    hs_code: Optional[str] = None
    cluster: Optional[str] = None
    normalized: str = ""
    aliases: tuple[str, ...] = ()

    # ★ ক্লাস্টারভুক্ত সকল এইচ.এস কোড ও নাম (শীট হইতে প্রাপ্ত)
    hs_codes: tuple[str, ...] = ()
    member_names: tuple[str, ...] = ()
    is_cluster: bool = False

    def __post_init__(self):
        if not self.normalized:
            self.normalized = normalize(self.name)
        if not self.hs_codes and self.hs_code:
            self.hs_codes = (self.hs_code,)
        if not self.member_names:
            self.member_names = (self.name,)
        # ক্লাস্টার লেবেল কেবল তথ্যমূলক — মিলকরণে ব্যবহৃত হয় না


# ==========================================================
# মূল Matcher
# ==========================================================

class ItemMatcher:
    """
    আমদানি আইটেমকে প্রাপ্যতা আইটেমের সাথে মেলায়।

    ব্যবহার:
        matcher = ItemMatcher(entitlement_candidates)
        result  = matcher.match("Grey Cotton Fabric", "5208.11.00")
    """

    # থ্রেশহোল্ড
    FUZZY_ACCEPT = 0.82      # এর উপরে হলে নিশ্চিত মিল
    FUZZY_SUGGEST = 0.62     # এর উপরে হলে সম্ভাব্য মিল (মানুষ যাচাই করবে)

    def __init__(
        self,
        candidates: Iterable[MatchCandidate],
        dictionary: dict[str, str] | None = None,
    ):
        self.candidates: list[MatchCandidate] = list(candidates)
        # বাণিজ্যিক নাম অভিধান: normalized_commercial → standard_name
        self.dictionary: dict[str, str] = dictionary or {}

        # দ্রুত lookup সূচক
        self._by_hs: dict[str, list[MatchCandidate]] = {}
        self._by_heading: dict[str, list[MatchCandidate]] = {}
        self._by_cluster: dict[str, list[MatchCandidate]] = {}

        for c in self.candidates:
            # ★ ক্লাস্টারের প্রতিটি সদস্য এইচ.এস কোড একই প্রার্থীতে নির্দেশ করে
            for hs in (c.hs_codes or ()):
                d = re.sub(r"\D", "", str(hs))
                if not d:
                    continue
                if c not in self._by_hs.setdefault(d, []):
                    self._by_hs[d].append(c)
                if len(d) >= 4:
                    lst = self._by_heading.setdefault(d[:4], [])
                    if c not in lst:
                        lst.append(c)
            if c.cluster:
                self._by_cluster.setdefault(c.cluster, []).append(c)

    # ------------------------------------------------------
    def match(
        self,
        item_name: str,
        hs_code: str | None = None,
        allow_cluster: bool = True,
        require_exact_hs: bool = False,
    ) -> MatchResult:
        """
        একটি আমদানি আইটেম মেলাও।

        স্তরক্রম: HS হুবহু → HS শিরোনাম → অভিধান → Fuzzy → ক্লাস্টার

        require_exact_hs : কঠোর মোড — এইচ.এস কোড থাকলে সেটি প্রাপ্যতা শীটে
                           হুবহু (বা শীটের কম-নির্দিষ্ট কোডের অধীনে) থাকতেই
                           হবে; নতুবা অননুমোদিত।
        """
        hs_digits = re.sub(r"\D", "", str(hs_code)) if hs_code else ""

        # ===== স্তর ১: HS কোড হুবহু মিল =====
        pool = self._lookup_hs(hs_digits) if hs_digits else []
        if pool:
            if len(pool) == 1:
                c = pool[0]
                note = (
                    f"HS কোড {hs_code} প্রাপ্যতা শীটের '{c.name}' "
                    f"ক্লাস্টারভুক্ত হিসেবে পাওয়া গেছে।"
                    if c.is_cluster else
                    f"HS কোড {hs_code} প্রাপ্যতা শীটে পাওয়া গেছে।"
                )
                return MatchResult(
                    True, c.id, c.name, c.hs_code, 1.00, "hs_exact", note,
                )
            best = self._best_by_name(item_name, pool)
            if best:
                c, s = best
                return MatchResult(
                    True, c.id, c.name, c.hs_code, max(0.90, s), "hs_exact",
                    f"HS কোড {hs_code} মিলেছে; একাধিক এন্ট্রির মধ্যে "
                    f"নামের সাদৃশ্য {s:.0%} অনুযায়ী নির্বাচিত।",
                )

        # ===== কঠোর মোড: HS আছে কিন্তু শীটে নেই → অননুমোদিত =====
        if require_exact_hs and hs_digits:
            return MatchResult(
                False, None, None, None, 0.0, "none",
                f"এইচ.এস কোড {hs_code} প্রাপ্যতা শীটে অন্তর্ভুক্ত নয় "
                f"('{item_name}')। শীটে উল্লিখিত কোডের বাইরে হওয়ায় "
                f"অননুমোদিত এইচ.এস কোড ব্যবহার করে আমদানি হিসেবে গণ্য।",
                alternatives=self._top_alternatives(item_name),
            )

        # ===== স্তর ২: বাণিজ্যিক নাম অভিধান =====
        norm_item = normalize(item_name)
        std = self.dictionary.get(norm_item)
        if std:
            std_norm = normalize(std)
            for c in self.candidates:
                if c.normalized == std_norm:
                    return MatchResult(
                        True, c.id, c.name, c.hs_code, 0.95, "dictionary",
                        f"বাণিজ্যিক নাম অভিধান অনুযায়ী "
                        f"'{item_name}' = '{std}' — পূর্বের অডিটে শেখা।",
                    )

        # ===== স্তর ৩: HS শিরোনাম (প্রথম ৪ সংখ্যা) =====
        if hs_digits and len(hs_digits) >= 4:
            pool = self._by_heading.get(hs_digits[:4], [])
            if pool:
                best = self._best_by_name(item_name, pool)
                if best and best[1] >= self.FUZZY_SUGGEST:
                    c, s = best
                    return MatchResult(
                        True, c.id, c.name, c.hs_code, min(0.88, 0.70 + s * 0.2),
                        "hs_heading",
                        f"HS শিরোনাম {hs_digits[:4]} মিলেছে (সম্পূর্ণ কোড ভিন্ন) "
                        f"এবং নামের সাদৃশ্য {s:.0%}।",
                    )

        # ===== স্তর ৪: Fuzzy নাম মিলকরণ =====
        best = self._best_by_name(item_name, self.candidates)
        if best:
            c, s = best
            if s >= self.FUZZY_ACCEPT:
                return MatchResult(
                    True, c.id, c.name, c.hs_code, s, "fuzzy_name",
                    f"নামের সাদৃশ্য {s:.0%} — '{item_name}' ≈ '{c.name}'।",
                    alternatives=self._top_alternatives(item_name, exclude=c.id),
                )

        # ===== স্তর ৫: ক্লাস্টার ভিত্তিক =====
        if allow_cluster:
            cluster, cconf = detect_cluster(item_name, hs_code)
            if cluster and cluster in self._by_cluster:
                pool = self._by_cluster[cluster]
                cand = self._best_by_name(item_name, pool)
                c = cand[0] if cand else pool[0]
                s = (cand[1] if cand else 0.3)
                score = min(0.70, 0.40 + cconf * 0.2 + s * 0.15)
                return MatchResult(
                    True, c.id, c.name, c.hs_code, score, "cluster",
                    f"সরাসরি মিল পাওয়া যায়নি; তবে উভয়ই '{cluster}' "
                    f"ক্লাস্টারভুক্ত — ক্লাস্টার ভিত্তিতে প্রাপ্যতার সাথে মেলানো হলো।",
                    alternatives=self._top_alternatives(item_name),
                )

        # ===== মিল নেই =====
        return MatchResult(
            False, None, None, None, 0.0, "none",
            f"'{item_name}' (HS {hs_code or '—'}) প্রাপ্যতা শীটে "
            f"কোনোভাবেই খুঁজে পাওয়া যায়নি।",
            alternatives=self._top_alternatives(item_name),
        )

    # ------------------------------------------------------
    def _lookup_hs(self, hs_digits: str) -> list[MatchCandidate]:
        """
        HS কোড দিয়ে প্রার্থী খোঁজো।

        হুবহু মিল ছাড়াও, প্রাপ্যতা শীটের কোড যদি কম-নির্দিষ্ট হয়
        (যেমন শীটে "5407" আর আমদানিতে "5407.61.00") তবে সেটিও গ্রহণযোগ্য —
        কারণ কম-নির্দিষ্ট কোড বৃহত্তর পরিসর নির্দেশ করে।
        তবে বিপরীতটি নয় (শীটে ৮ সংখ্যা, আমদানিতে ভিন্ন ৮ সংখ্যা)।
        """
        if not hs_digits:
            return []
        if hs_digits in self._by_hs:
            return self._by_hs[hs_digits]
        # শীটের কোড আমদানি কোডের উপসর্গ কিনা
        out: list[MatchCandidate] = []
        for code, cands in self._by_hs.items():
            if len(code) < len(hs_digits) and hs_digits.startswith(code):
                out.extend(cands)
        return out

    # ------------------------------------------------------
    def _best_by_name(
        self, item_name: str, pool: list[MatchCandidate]
    ) -> Optional[tuple[MatchCandidate, float]]:
        """নামের ভিত্তিতে সেরা প্রার্থী"""
        n = normalize(item_name)
        if not n or not pool:
            return None
        best_c, best_s = None, 0.0
        for c in pool:
            if not c.normalized:
                continue
            s = _ratio(n, c.normalized)
            # আংশিক মিলও বিবেচনা (একটি নাম অন্যটির ভেতরে থাকলে)
            p = _partial(n, c.normalized)
            s = max(s, p * 0.92)
            # উপনাম ও ক্লাস্টার-সদস্যদের নামের সাথে মিল
            for alias in tuple(c.aliases) + tuple(c.member_names or ()):
                if alias:
                    s = max(s, _ratio(n, normalize(alias)))
            if s > best_s:
                best_c, best_s = c, s
        return (best_c, best_s) if best_c else None

    # ------------------------------------------------------
    def _top_alternatives(
        self, item_name: str, exclude: int | None = None, k: int = 3
    ) -> list[dict]:
        """সম্ভাব্য বিকল্প মিল — মানুষ যাচাই করতে পারবে"""
        n = normalize(item_name)
        scored = []
        for c in self.candidates:
            if exclude is not None and c.id == exclude:
                continue
            if not c.normalized:
                continue
            s = max(_ratio(n, c.normalized), _partial(n, c.normalized) * 0.92)
            if s >= self.FUZZY_SUGGEST:
                scored.append({
                    "id": c.id, "name": c.name,
                    "hs_code": c.hs_code, "score": round(s, 3),
                })
        scored.sort(key=lambda x: -x["score"])
        return scored[:k]


__all__ = [
    "normalize", "detect_cluster", "ClusterRule", "DEFAULT_CLUSTERS",
    "ItemMatcher", "MatchCandidate", "MatchResult", "HAS_RAPIDFUZZ",
    "is_machinery", "MACHINERY_HS_CHAPTERS", "MACHINERY_KEYWORDS",
]
