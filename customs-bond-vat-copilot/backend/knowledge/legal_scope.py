"""
Legal Scope Engine — আইনি পরিধি নির্ধারক
==========================================

উদ্দেশ্য:
    নিরীক্ষা শুরুর পূর্বেই ইঞ্জিন নির্ধারণ করিবে কোন কোন আইন, বিধিমালা
    ও এসআরও উক্ত প্রতিষ্ঠান ও নিরীক্ষার জন্য প্রাসঙ্গিক।

মূল নীতি (ব্যবহারকারী কর্তৃক নির্ধারিত):

    ১) ভ্যাট নিরীক্ষায় বন্ড-সংক্রান্ত আইন-বিধি প্রযোজ্য নহে
       (কাস্টমস আইন, ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ইপিজেড বিধিমালা)।

    ২) বন্ড প্রতিষ্ঠানের নিরীক্ষায় ভ্যাট আইন ও বিধিমালা প্রযোজ্য থাকিবে।

    ৩) ইপিজেডের বাহিরে অবস্থিত প্রতিষ্ঠানের ক্ষেত্রে ইপিজেড বিধিমালা
       প্রযোজ্য নহে।

এই মডিউল কোনো আইন "ব্যাখ্যা" করে না — শুধু প্রাসঙ্গিকতা নির্ধারণ করে
এবং সংশ্লিষ্ট বিধানের উদ্ধৃতি সরবরাহ করে। ব্যাখ্যা ও প্রয়োগের দায়িত্ব
নিরীক্ষকের।
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


# ==========================================================
# নিরীক্ষা ও প্রতিষ্ঠানের প্রেক্ষাপট
# ==========================================================

class AuditType(str, enum.Enum):
    """নিরীক্ষার ধরন"""
    BOND = "bond"            # বন্ড নিরীক্ষা (ভ্যাট আইনও প্রযোজ্য)
    VAT = "vat"              # ভ্যাট নিরীক্ষা (বন্ড আইন প্রযোজ্য নহে)
    BOND_VAT = "bond_vat"    # সমন্বিত নিরীক্ষা


class ZoneType(str, enum.Enum):
    """প্রতিষ্ঠানের অবস্থান"""
    GENERAL = "general"      # সাধারণ এলাকা (ইপিজেডের বাহিরে)
    EPZ = "epz"              # রপ্তানি প্রক্রিয়াকরণ এলাকা
    EZ = "ez"                # অর্থনৈতিক অঞ্চল
    HITECH = "hitech"        # হাই-টেক পার্ক


class BondType(str, enum.Enum):
    """বন্ডের ধরন"""
    GENERAL_BOND = "general_bond"          # সাধারণ বন্ডেড ওয়্যারহাউস
    SPECIAL_BOND = "special_bond"          # বিশেষ বন্ডেড ওয়্যারহাউস
    DIPLOMATIC = "diplomatic"              # কূটনৈতিক বন্ড
    HOME_CONSUMPTION = "home_consumption"  # হোম কনজাম্পশন বন্ড
    NOT_BONDED = "not_bonded"              # বন্ডবিহীন (শুধু ভ্যাট নিবন্ধিত)


@dataclass
class AuditContext:
    """
    নিরীক্ষার প্রেক্ষাপট — ইহার ভিত্তিতেই আইনি পরিধি নির্ধারিত হয়।
    ব্যবহারকারী নিরীক্ষা শুরুর সময় এই তথ্য দিবেন।
    """
    audit_type: AuditType = AuditType.BOND
    zone: ZoneType = ZoneType.GENERAL
    bond_type: BondType = BondType.GENERAL_BOND

    # শিল্পের ধরন — কিছু এসআরও শিল্পভিত্তিক
    industry: str = "garments"

    # অতিরিক্ত বৈশিষ্ট্য
    is_exporter: bool = True
    is_deemed_exporter: bool = False
    has_local_sales: bool = False

    # নিরীক্ষার মেয়াদ — সময়ভিত্তিক প্রযোজ্যতা যাচাইয়ের জন্য
    period_from: Optional[str] = None
    period_to: Optional[str] = None

    @property
    def is_bond_audit(self) -> bool:
        return self.audit_type in (AuditType.BOND, AuditType.BOND_VAT)

    @property
    def is_vat_audit(self) -> bool:
        return self.audit_type in (AuditType.VAT, AuditType.BOND_VAT)

    @property
    def is_epz(self) -> bool:
        return self.zone in (ZoneType.EPZ, ZoneType.EZ, ZoneType.HITECH)


# ==========================================================
# আইনের শ্রেণী
# ==========================================================

class LawDomain(str, enum.Enum):
    """আইনের বিষয়ক্ষেত্র"""
    CUSTOMS = "customs"          # কাস্টমস / শুল্ক
    BOND = "bond"                # বন্ড ও ওয়্যারহাউস
    VAT = "vat"                  # মূল্য সংযোজন কর
    EPZ = "epz"                  # ইপিজেড / অর্থনৈতিক অঞ্চল
    INCOME_TAX = "income_tax"    # আয়কর
    GENERAL = "general"          # সাধারণ / পদ্ধতিগত


class LawKind(str, enum.Enum):
    """দলিলের ধরন"""
    ACT = "act"                  # আইন
    RULES = "rules"              # বিধিমালা
    SRO = "sro"                  # প্রজ্ঞাপন
    ORDER = "order"              # আদেশ
    CIRCULAR = "circular"        # পরিপত্র
    MANUAL = "manual"            # ম্যানুয়াল / নির্দেশিকা


@dataclass
class LawSource:
    """একটি আইনি দলিলের পরিচয়"""
    code: str                    # অভ্যন্তরীণ সংক্ষিপ্ত কোড
    title_bn: str                # বাংলা পূর্ণ নাম
    title_en: str = ""
    kind: LawKind = LawKind.ACT
    domain: LawDomain = LawDomain.GENERAL
    year: str = ""
    number: str = ""             # এসআরও নম্বর ইত্যাদি

    # প্রযোজ্যতার শর্ত
    applies_to_zones: tuple[ZoneType, ...] = ()      # খালি = সব অঞ্চল
    excluded_zones: tuple[ZoneType, ...] = ()
    applies_to_bond_types: tuple[BondType, ...] = ()
    industries: tuple[str, ...] = ()                 # খালি = সব শিল্প

    # নথিপত্র
    file_path: str = ""
    citation_format: str = ""    # উদ্ধৃতির আদর্শ রূপ
    notes: str = ""

    def citation(self, section: str = "") -> str:
        """আদর্শ উদ্ধৃতি তৈরি করো"""
        if self.citation_format:
            base = self.citation_format
        elif self.kind == LawKind.SRO:
            base = f"এসআরও নং {self.number}/{self.year}"
        elif self.kind == LawKind.RULES:
            base = f"{self.title_bn}"
        else:
            base = f"{self.title_bn}"
        return f"{base}, {section}" if section else base


# ==========================================================
# আইনি দলিলের নিবন্ধন
# ==========================================================
# ব্যবহারকারী কর্তৃক সরবরাহিত দলিলসমূহ।
# PDF আপলোড হইলে এই তালিকার সহিত সংযুক্ত হইবে।

LAW_REGISTRY: dict[str, LawSource] = {

    # ---------- কাস্টমস ----------
    "CUSTOMS_ACT_2023": LawSource(
        code="CUSTOMS_ACT_2023",
        title_bn="কাস্টমস আইন, ২০২৩",
        title_en="The Customs Act, 2023",
        kind=LawKind.ACT, domain=LawDomain.CUSTOMS, year="2023",
        citation_format="কাস্টমস আইন, ২০২৩",
    ),

    # ---------- বন্ড ও ওয়্যারহাউস ----------
    "WH_LICENSING_RULES_2024": LawSource(
        code="WH_LICENSING_RULES_2024",
        title_bn="বন্ডেড ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪",
        title_en="Bonded Warehouse Licensing Rules, 2024",
        kind=LawKind.RULES, domain=LawDomain.BOND, year="2024",
        citation_format="বন্ডেড ওয়্যারহাউস লাইসেন্সিং বিধিমালা, ২০২৪",
    ),
    "SRO_212_2024": LawSource(
        code="SRO_212_2024",
        title_bn="এসআরও নং ২১২-আইন/২০২৪/…/কাস্টমস",
        kind=LawKind.SRO, domain=LawDomain.BOND,
        year="2024", number="২১২",
        citation_format="এসআরও নং ২১২-আইন/২০২৪",
        notes="বন্ড সংক্রান্ত প্রধান এসআরও — সর্বাধিক ব্যবহৃত",
    ),

    # ---------- ভ্যাট ----------
    "VAT_ACT_2012": LawSource(
        code="VAT_ACT_2012",
        title_bn="মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন, ২০১২",
        title_en="Value Added Tax and Supplementary Duty Act, 2012",
        kind=LawKind.ACT, domain=LawDomain.VAT, year="2012",
        citation_format="মূল্য সংযোজন কর ও সম্পূরক শুল্ক আইন, ২০১২",
    ),
    "VAT_RULES_2016": LawSource(
        code="VAT_RULES_2016",
        title_bn="মূল্য সংযোজন কর ও সম্পূরক শুল্ক বিধিমালা, ২০১৬",
        title_en="Value Added Tax and Supplementary Duty Rules, 2016",
        kind=LawKind.RULES, domain=LawDomain.VAT, year="2016",
        citation_format="মূল্য সংযোজন কর ও সম্পূরক শুল্ক বিধিমালা, ২০১৬",
    ),
    "VAT_AUDIT_MANUAL_2022": LawSource(
        code="VAT_AUDIT_MANUAL_2022",
        title_bn="ভ্যাট নিরীক্ষা ম্যানুয়াল, ২০২২",
        title_en="VAT Audit Manual, 2022",
        kind=LawKind.MANUAL, domain=LawDomain.VAT, year="2022",
        citation_format="ভ্যাট নিরীক্ষা ম্যানুয়াল, ২০২২",
        notes="পদ্ধতিগত নির্দেশিকা — আইনি বাধ্যবাধকতা নহে",
    ),

    # ---------- ইপিজেড ----------
    "EPZ_RULES": LawSource(
        code="EPZ_RULES",
        title_bn="ইপিজেড সংক্রান্ত বিধিমালা",
        kind=LawKind.RULES, domain=LawDomain.EPZ,
        applies_to_zones=(ZoneType.EPZ, ZoneType.EZ, ZoneType.HITECH),
        notes="কেবল ইপিজেড/অর্থনৈতিক অঞ্চলভুক্ত প্রতিষ্ঠানের জন্য",
    ),
    "EPZ_SRO": LawSource(
        code="EPZ_SRO",
        title_bn="ইপিজেড সংক্রান্ত এসআরও",
        kind=LawKind.SRO, domain=LawDomain.EPZ,
        applies_to_zones=(ZoneType.EPZ, ZoneType.EZ, ZoneType.HITECH),
    ),
}


# ==========================================================
# প্রযোজ্যতা নির্ধারক
# ==========================================================

@dataclass
class ScopeDecision:
    """একটি আইনি দলিলের প্রযোজ্যতা সিদ্ধান্ত — ব্যাখ্যাসহ"""
    code: str
    title: str
    applicable: bool
    reason: str
    domain: str = ""
    kind: str = ""


class LegalScopeEngine:
    """
    নিরীক্ষার প্রেক্ষাপট অনুযায়ী প্রাসঙ্গিক আইন নির্ধারণ করে।

    ব্যবহার:
        ctx = AuditContext(audit_type=AuditType.BOND, zone=ZoneType.GENERAL)
        scope = LegalScopeEngine(ctx)
        for d in scope.decisions():
            print(d.title, d.applicable, d.reason)
    """

    def __init__(self, context: AuditContext, registry: dict = None):
        self.ctx = context
        self.registry = registry or LAW_REGISTRY

    # ------------------------------------------------------
    def decisions(self) -> list[ScopeDecision]:
        """প্রতিটি দলিলের প্রযোজ্যতা ও কারণ"""
        out: list[ScopeDecision] = []
        for code, law in self.registry.items():
            ok, reason = self._evaluate(law)
            out.append(ScopeDecision(
                code=code, title=law.title_bn, applicable=ok, reason=reason,
                domain=law.domain.value, kind=law.kind.value,
            ))
        # প্রযোজ্যগুলো আগে
        out.sort(key=lambda d: (not d.applicable, d.domain, d.code))
        return out

    # ------------------------------------------------------
    def applicable_codes(self) -> list[str]:
        """শুধু প্রযোজ্য দলিলের কোড"""
        return [d.code for d in self.decisions() if d.applicable]

    def applicable_laws(self) -> list[LawSource]:
        return [self.registry[c] for c in self.applicable_codes()]

    # ------------------------------------------------------
    def _evaluate(self, law: LawSource) -> tuple[bool, str]:
        """একটি দলিল প্রযোজ্য কিনা — কারণসহ"""
        ctx = self.ctx

        # ===== নিয়ম ১: ভ্যাট নিরীক্ষায় বন্ড-সংক্রান্ত আইন প্রযোজ্য নহে =====
        if ctx.audit_type == AuditType.VAT:
            if law.domain in (LawDomain.CUSTOMS, LawDomain.BOND, LawDomain.EPZ):
                return False, (
                    "ভ্যাট নিরীক্ষা হওয়ায় বন্ড/কাস্টমস/ইপিজেড সংক্রান্ত "
                    "আইন-বিধি প্রযোজ্য নহে।"
                )

        # ===== নিয়ম ২: বন্ড নিরীক্ষায় ভ্যাট আইন প্রযোজ্য =====
        if ctx.is_bond_audit and law.domain == LawDomain.VAT:
            return True, (
                "বন্ড প্রতিষ্ঠানের নিরীক্ষায় মূল্য সংযোজন কর সংক্রান্ত "
                "আইন ও বিধিমালা সমভাবে প্রযোজ্য।"
            )

        # ===== নিয়ম ৩: ইপিজেডের বাহিরে ইপিজেড বিধিমালা প্রযোজ্য নহে =====
        if law.domain == LawDomain.EPZ and not ctx.is_epz:
            return False, (
                f"প্রতিষ্ঠানটি ইপিজেড/অর্থনৈতিক অঞ্চলের বাহিরে "
                f"({ctx.zone.value}) অবস্থিত হওয়ায় প্রযোজ্য নহে।"
            )

        # ===== অঞ্চলভিত্তিক সীমাবদ্ধতা =====
        if law.applies_to_zones and ctx.zone not in law.applies_to_zones:
            return False, (
                f"এই বিধান কেবল "
                f"{', '.join(z.value for z in law.applies_to_zones)} "
                f"অঞ্চলের জন্য প্রযোজ্য।"
            )
        if law.excluded_zones and ctx.zone in law.excluded_zones:
            return False, f"{ctx.zone.value} অঞ্চলের জন্য এই বিধান রহিত।"

        # ===== বন্ডের ধরনভিত্তিক =====
        if law.applies_to_bond_types and ctx.bond_type not in law.applies_to_bond_types:
            return False, (
                f"এই বিধান কেবল "
                f"{', '.join(b.value for b in law.applies_to_bond_types)} "
                f"ধরনের বন্ডের জন্য প্রযোজ্য।"
            )

        # ===== শিল্পভিত্তিক =====
        if law.industries and ctx.industry not in law.industries:
            return False, (
                f"এই বিধান কেবল {', '.join(law.industries)} "
                f"শিল্পের জন্য প্রযোজ্য।"
            )

        # ===== বন্ড নিরীক্ষায় বন্ড/কাস্টমস আইন =====
        if ctx.is_bond_audit and law.domain in (LawDomain.BOND, LawDomain.CUSTOMS):
            return True, "বন্ড নিরীক্ষার মূল আইনি ভিত্তি।"

        return True, "নিরীক্ষার প্রেক্ষাপটে প্রাসঙ্গিক।"

    # ------------------------------------------------------
    def summary(self) -> dict:
        """UI-তে দেখানোর জন্য সারসংক্ষেপ"""
        ds = self.decisions()
        applicable = [d for d in ds if d.applicable]
        excluded = [d for d in ds if not d.applicable]
        return {
            "নিরীক্ষার ধরন": self.ctx.audit_type.value,
            "অবস্থান": self.ctx.zone.value,
            "বন্ডের ধরন": self.ctx.bond_type.value,
            "প্রযোজ্য দলিল সংখ্যা": len(applicable),
            "অপ্রযোজ্য দলিল সংখ্যা": len(excluded),
            "প্রযোজ্য দলিলসমূহ": [d.title for d in applicable],
            "অপ্রযোজ্য দলিলসমূহ": [
                {"দলিল": d.title, "কারণ": d.reason} for d in excluded
            ],
        }


__all__ = [
    "AuditType", "ZoneType", "BondType", "AuditContext",
    "LawDomain", "LawKind", "LawSource", "LAW_REGISTRY",
    "LegalScopeEngine", "ScopeDecision",
]
