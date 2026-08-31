"""
Audit Agent Core — নিরীক্ষা এজেন্টের কেন্দ্র
==============================================

ইহা কেবল চ্যাটবট নহে — একটি কর্মক্ষম এজেন্ট। ইহা পারে:

    • নিরীক্ষা সংক্রান্ত প্রশ্নের উত্তর দিতে (আইন ও নিয়ম সহকারে)
    • ইঞ্জিনের কার্যাবলি সম্পাদন করিতে (ফাইল বিশ্লেষণ, হিসাব, প্রতিবেদন)
    • নিরীক্ষক কর্তৃক শেখানো নিয়ম আয়ত্ত করিয়া পরবর্তীতে প্রয়োগ করিতে
    • প্রতিটি উত্তরের ভিত্তি ও উৎস দেখাইতে (Explainable)

স্তরবিন্যাস:
    স্তর ১ — নিয়ম ইঞ্জিন (সম্পূর্ণ অফলাইন, তাৎক্ষণিক, নিশ্চিত)
    স্তর ২ — স্থানীয় এলএলএম (Ollama — অফলাইন, ভাষা ও যুক্তি)
    স্তর ৩ — ক্লাউড এলএলএম (ঐচ্ছিক, কেবল নিরীক্ষক অনুমোদন করিলে)

★ গোপনীয়তা প্রহরী:
    নিরীক্ষার গোপন তথ্য (প্রতিষ্ঠানের নাম, অঙ্ক, ফাইন্ডিংস) কখনোই
    যন্ত্রের বাহিরে যাইবে না। ক্লাউড স্তর ব্যবহারের পূর্বে তথ্য
    পরীক্ষা করিয়া গোপন অংশ থাকিলে প্রেরণ আটকাইয়া দেওয়া হয়।
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from utils.logger import logger


# ==========================================================
# গোপনীয়তা প্রহরী
# ==========================================================

# গোপন তথ্যের সংকেত — এইগুলি থাকিলে ক্লাউডে পাঠানো নিষেধ
_SENSITIVE_PATTERNS = [
    (r"\bBIN[\s:]*\d{6,}", "ব্যবসা শনাক্তকরণ নম্বর"),
    (r"\bTIN[\s:]*\d{6,}", "কর শনাক্তকরণ নম্বর"),
    (r"বন্ড\s*লাইসেন্স\s*(নং|নম্বর)?[\s:]*[\w/\-]+", "বন্ড লাইসেন্স নম্বর"),
    (r"\b[A-Z]{1,3}[-/]?\d{5,}\b", "বিল অব এন্ট্রি নম্বর"),
    (r"৳\s*[\d,]{6,}", "টাকার অঙ্ক"),
    (r"\b\d{1,3}(,\d{2,3})+(\.\d+)?\b", "বড় সংখ্যা"),
    (r"\bLtd\.?\b|\bLimited\b|লিমিটেড", "প্রতিষ্ঠানের নাম"),
]


@dataclass
class PrivacyCheck:
    """গোপনীয়তা যাচাইয়ের ফলাফল"""
    is_safe: bool = True
    found: list[str] = field(default_factory=list)
    reason: str = ""


def check_privacy(text: str | None) -> PrivacyCheck:
    """
    লেখায় নিরীক্ষার গোপন তথ্য আছে কিনা যাচাই করো।
    ক্লাউড স্তরে পাঠাইবার পূর্বে ইহা অবশ্যই চালাইতে হইবে।
    """
    chk = PrivacyCheck()
    if not text:
        return chk
    for pat, label in _SENSITIVE_PATTERNS:
        if re.search(pat, str(text), flags=re.IGNORECASE):
            chk.found.append(label)
    if chk.found:
        chk.is_safe = False
        chk.reason = (
            "বার্তায় নিরীক্ষার গোপন তথ্য পাওয়া গিয়াছে ("
            + ", ".join(dict.fromkeys(chk.found))
            + ")। দাপ্তরিক গোপনীয়তা রক্ষার্থে ইহা যন্ত্রের বাহিরে "
            "প্রেরণ করা হয় নাই; স্থানীয় মডেল দিয়াই উত্তর প্রস্তুত হইয়াছে।"
        )
    return chk


# ==========================================================
# টুল সংজ্ঞা
# ==========================================================

@dataclass
class AgentTool:
    """এজেন্ট যে কাজগুলি করিতে পারে"""
    name: str
    description: str
    parameters: dict
    handler: Callable
    requires_confirm: bool = False   # ধ্বংসাত্মক কাজে নিশ্চিতকরণ
    category: str = "general"

    def to_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """এজেন্টের টুল-ভান্ডার"""

    def __init__(self):
        self.tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool):
        self.tools[tool.name] = tool
        return tool

    def add(
        self, name: str, description: str, parameters: dict,
        category: str = "general", requires_confirm: bool = False,
    ):
        """ডেকোরেটর হিসাবে ব্যবহারযোগ্য"""
        def deco(fn: Callable):
            self.register(AgentTool(
                name=name, description=description, parameters=parameters,
                handler=fn, category=category, requires_confirm=requires_confirm,
            ))
            return fn
        return deco

    def schemas(self) -> list[dict]:
        return [t.to_schema() for t in self.tools.values()]

    def call(self, name: str, args: dict) -> dict:
        """একটি টুল চালাও — ত্রুটি নিরাপদে ধরা হয়"""
        tool = self.tools.get(name)
        if not tool:
            return {"ok": False, "error": f"'{name}' নামে কোনো টুল নাই"}
        try:
            t0 = time.time()
            result = tool.handler(**(args or {}))
            return {
                "ok": True, "tool": name, "result": result,
                "elapsed_ms": int((time.time() - t0) * 1000),
            }
        except TypeError as e:
            return {"ok": False, "tool": name, "error": f"ভুল প্যারামিটার: {e}"}
        except Exception as e:
            logger.exception(f"টুল ব্যর্থ: {name}")
            return {"ok": False, "tool": name, "error": str(e)}


# ==========================================================
# এলএলএম সরবরাহকারী
# ==========================================================

class LLMProvider:
    """এলএলএম সরবরাহকারীর সাধারণ রূপ"""
    name = "base"
    is_local = True

    def available(self) -> bool:
        raise NotImplementedError

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             **kw) -> dict:
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    """
    স্থানীয় এলএলএম — সম্পূর্ণ অফলাইন।

    যন্ত্রের RAM অনুযায়ী মডেল বাছাই করে।
    """
    name = "ollama"
    is_local = True

    # RAM (গিগাবাইট) → সুপারিশকৃত মডেল
    MODEL_BY_RAM = [
        (28, "qwen2.5:32b-instruct-q4_K_M"),
        (20, "qwen2.5:14b-instruct-q4_K_M"),
        (12, "llama3.1:8b-instruct-q4_K_M"),
        (6,  "llama3.2:3b-instruct-q4_K_M"),
        (0,  "llama3.2:1b"),
    ]

    def __init__(self, host: str = "http://localhost:11434",
                 model: str | None = None, timeout: int = 180):
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.model = model or self._pick_model()

    # ------------------------------------------------------
    @staticmethod
    def detect_ram_gb() -> float:
        """যন্ত্রের মোট RAM (গিগাবাইট)"""
        try:
            import psutil
            return psutil.virtual_memory().total / (1024 ** 3)
        except ImportError:
            pass
        try:
            import os
            if hasattr(os, "sysconf"):
                pages = os.sysconf("SC_PHYS_PAGES")
                size = os.sysconf("SC_PAGE_SIZE")
                return pages * size / (1024 ** 3)
        except Exception:
            pass
        return 8.0     # নিরাপদ অনুমান

    def _pick_model(self) -> str:
        ram = self.detect_ram_gb()
        for need, model in self.MODEL_BY_RAM:
            if ram >= need:
                logger.info(
                    f"যন্ত্রে {ram:.0f} GB RAM — মডেল নির্বাচিত: {model}"
                )
                return model
        return "llama3.2:1b"

    # ------------------------------------------------------
    def available(self) -> bool:
        try:
            import httpx
            r = httpx.get(f"{self.host}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            import httpx
            r = httpx.get(f"{self.host}/api/tags", timeout=5)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    # ------------------------------------------------------
    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             temperature: float = 0.2, **kw) -> dict:
        import httpx
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 8192},
        }
        if tools:
            payload["tools"] = tools

        r = httpx.post(
            f"{self.host}/api/chat", json=payload, timeout=self.timeout
        )
        r.raise_for_status()
        data = r.json()
        msg = data.get("message", {}) or {}
        return {
            "content": msg.get("content", ""),
            "tool_calls": msg.get("tool_calls") or [],
            "model": data.get("model", self.model),
            "provider": "ollama",
        }


class CloudProvider(LLMProvider):
    """
    ক্লাউড এলএলএম — কেবল নিরীক্ষক স্পষ্টভাবে অনুমোদন করিলে।

    ★ গোপনীয়তা প্রহরী দ্বারা সুরক্ষিত — গোপন তথ্য থাকিলে
      প্রেরণ আটকাইয়া দেওয়া হয়।
    """
    name = "cloud"
    is_local = False

    def __init__(self, vendor: str = "anthropic", api_key: str = "",
                 model: str = "", enabled: bool = False):
        self.vendor = vendor
        self.api_key = api_key
        self.model = model or {
            "anthropic": "claude-sonnet-4-5",
            "openai": "gpt-4o",
            "gemini": "gemini-2.0-flash",
        }.get(vendor, "")
        self.enabled = enabled

    def available(self) -> bool:
        return bool(self.enabled and self.api_key)

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             **kw) -> dict:
        if not self.available():
            raise RuntimeError("ক্লাউড স্তর সক্রিয় নাই বা API key দেওয়া হয় নাই")

        # ★ প্রেরণের পূর্বে গোপনীয়তা যাচাই — ব্যতিক্রমহীন
        blob = "\n".join(str(m.get("content", "")) for m in messages)
        chk = check_privacy(blob)
        if not chk.is_safe:
            raise PermissionError(chk.reason)

        import httpx
        if self.vendor == "anthropic":
            sys_msgs = [m["content"] for m in messages if m["role"] == "system"]
            conv = [m for m in messages if m["role"] != "system"]
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model, "max_tokens": 4000,
                    "system": "\n\n".join(sys_msgs),
                    "messages": conv,
                },
                timeout=120,
            )
            r.raise_for_status()
            d = r.json()
            text = "".join(
                b.get("text", "") for b in d.get("content", [])
                if b.get("type") == "text"
            )
            return {"content": text, "tool_calls": [],
                    "model": self.model, "provider": "anthropic"}

        raise NotImplementedError(f"'{self.vendor}' এখনো সমর্থিত নহে")


# ==========================================================
# কথোপকথন
# ==========================================================

@dataclass
class AgentMessage:
    role: str                       # user | assistant | system | tool
    content: str = ""
    tool_calls: list = field(default_factory=list)
    tool_name: str = ""
    timestamp: str = ""
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat(timespec="seconds")


@dataclass
class AgentReply:
    """এজেন্টের একটি উত্তর — সম্পূর্ণ ব্যাখ্যাসহ"""
    text: str = ""
    provider: str = ""
    model: str = ""

    # ব্যাখ্যা
    applied_rules: list[int] = field(default_factory=list)
    rule_summaries: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)

    # শেখা
    rule_detected: bool = False
    rule_proposal: dict = field(default_factory=dict)

    # নিরাপত্তা
    privacy_blocked: bool = False
    privacy_note: str = ""

    elapsed_ms: int = 0
    error: str = ""


# ==========================================================
# সিস্টেম নির্দেশনা
# ==========================================================

SYSTEM_PROMPT = """তুমি একজন অভিজ্ঞ বাংলাদেশ কাস্টমস বন্ড ও মূল্য সংযোজন কর
নিরীক্ষা সহকারী। তোমার নাম "নিরীক্ষা সহায়ক"।

তোমার দায়িত্ব:
  • বন্ড ও ভ্যাট নিরীক্ষা সংক্রান্ত প্রশ্নের সঠিক উত্তর দেওয়া
  • প্রযোজ্য আইন, বিধি ও এসআরও উদ্ধৃত করা
  • হিসাব-নিকাশে সহায়তা করা
  • প্রয়োজনে টুল ব্যবহার করিয়া প্রকৃত তথ্য বাহির করা

অবশ্যপালনীয় নিয়ম:
  ১। উত্তর বাংলায় দিবে; কেবল কারিগরি ও আইনি পরিভাষা ইংরেজিতে থাকিতে পারে।
  ২। আইন উদ্ধৃত করিবার সময় এসআরও নম্বর ও বিধি নম্বর নির্ভুলভাবে লিখিবে।
     নিশ্চিত না হইলে স্পষ্টভাবে বলিবে "যাচাই করা প্রয়োজন" — অনুমান করিয়া
     আইনের ধারা বলিবে না।
  ৩। কোনো সংখ্যা বা হিসাব দিবার সময় উহার ভিত্তি ও সূত্র দেখাইবে।
  ৪। নিরীক্ষকের শেখানো নিয়ম সর্বোচ্চ অগ্রাধিকার পাইবে — উহা আইনের
     ব্যাখ্যা সম্পর্কে তোমার নিজস্ব ধারণার চেয়েও অগ্রগণ্য।
  ৫। জানা না থাকিলে সরাসরি বলিবে "আমি নিশ্চিত নহি"। বানাইয়া বলিবে না।
  ৬। তুমি আইনি সিদ্ধান্ত দাও না — তথ্য ও বিশ্লেষণ উপস্থাপন কর।
     চূড়ান্ত সিদ্ধান্ত নিরীক্ষকের।

লেখার ধরন:
  • প্রতিবেদনের জন্য সাধু ভাষা, কথোপকথনে সহজ চলিত ভাষা
  • সংক্ষিপ্ত ও স্পষ্ট; অপ্রয়োজনীয় ভূমিকা নহে
"""


# ==========================================================
# এজেন্ট
# ==========================================================

class AuditAgent:
    """
    নিরীক্ষা এজেন্ট।

    ব্যবহার:
        agent = AuditAgent(rule_store=store, tools=registry)
        reply = agent.ask("এককালীন বন্ডিং ক্যাপাসিটি কীভাবে নির্ণয় হয়?")
    """

    MAX_TOOL_ROUNDS = 4
    MAX_HISTORY = 20

    def __init__(
        self,
        rule_store=None,
        tools: ToolRegistry | None = None,
        local_provider: LLMProvider | None = None,
        cloud_provider: LLMProvider | None = None,
        session_ref: str = "",
    ):
        self.rules = rule_store
        self.tools = tools or ToolRegistry()
        self.local = local_provider or OllamaProvider()
        self.cloud = cloud_provider
        self.session_ref = session_ref
        self.history: list[AgentMessage] = []

    # ------------------------------------------------------
    def ask(
        self, question: str, scope: str | None = None,
        allow_cloud: bool = False, allow_tools: bool = True,
    ) -> AgentReply:
        """এজেন্টকে প্রশ্ন করো"""
        t0 = time.time()
        reply = AgentReply()

        if not question or not question.strip():
            reply.error = "প্রশ্ন খালি"
            return reply

        # ---- ১) নিয়ম শনাক্তকরণ (নিরীক্ষক কিছু শেখাইতেছেন?) ----
        if self.rules is not None:
            try:
                from knowledge.learned_rules import detect_rule
                det = detect_rule(question)
                if det.is_rule:
                    reply.rule_detected = True
                    reply.rule_proposal = {
                        "scope": det.scope, "kind": det.kind,
                        "confidence": round(det.confidence, 2),
                        "summary": det.suggested_summary,
                        "statement": question.strip(),
                    }
            except Exception as e:
                logger.warning(f"নিয়ম শনাক্তকরণ ব্যর্থ: {e}")

        # ---- ২) প্রাসঙ্গিক শেখা নিয়ম সংগ্রহ ----
        rule_ctx = ""
        if self.rules is not None:
            try:
                from knowledge.learned_rules import build_rule_context
                rule_ctx, ids = build_rule_context(self.rules, question, scope)
                reply.applied_rules = ids
                if ids:
                    reply.rule_summaries = [
                        r.summary for r in
                        (self.rules.get(i) for i in ids) if r
                    ]
            except Exception as e:
                logger.warning(f"নিয়ম উদ্ধার ব্যর্থ: {e}")

        # ---- ৩) বার্তা প্রস্তুত ----
        messages = self._build_messages(question, rule_ctx)

        # ---- ৪) সরবরাহকারী নির্বাচন ----
        provider, note = self._choose_provider(question, allow_cloud)
        if provider is None:
            reply.error = note
            reply.text = self._fallback_answer(question, rule_ctx)
            reply.provider = "rules_only"
            reply.elapsed_ms = int((time.time() - t0) * 1000)
            return reply
        reply.privacy_note = note

        # ---- ৫) সংলাপ ও টুল চালনা ----
        try:
            tool_schemas = self.tools.schemas() if (
                allow_tools and provider.is_local and self.tools.tools
            ) else None

            for _ in range(self.MAX_TOOL_ROUNDS):
                out = provider.chat(messages, tools=tool_schemas)
                reply.provider = out.get("provider", provider.name)
                reply.model = out.get("model", "")

                calls = out.get("tool_calls") or []
                if not calls:
                    reply.text = (out.get("content") or "").strip()
                    break

                messages.append({
                    "role": "assistant", "content": out.get("content", ""),
                    "tool_calls": calls,
                })
                for c in calls:
                    fn = (c.get("function") or {})
                    name = fn.get("name", "")
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    res = self.tools.call(name, args)
                    reply.tools_used.append(name)
                    reply.tool_results.append(res)
                    messages.append({
                        "role": "tool", "name": name,
                        "content": json.dumps(res, ensure_ascii=False)[:4000],
                    })
            else:
                reply.text = (
                    "একাধিকবার টুল ব্যবহার করিয়াও চূড়ান্ত উত্তরে পৌঁছানো "
                    "যায় নাই। অনুগ্রহ করিয়া প্রশ্নটি আরও নির্দিষ্ট করুন।"
                )

        except PermissionError as e:
            reply.privacy_blocked = True
            reply.privacy_note = str(e)
            reply.text = self._fallback_answer(question, rule_ctx)
            reply.provider = "rules_only"
        except Exception as e:
            logger.exception("এজেন্ট ব্যর্থ")
            reply.error = str(e)
            reply.text = self._fallback_answer(question, rule_ctx)
            reply.provider = "rules_only"

        # ---- ৬) হিসাব রাখা ----
        if reply.applied_rules and self.rules is not None:
            try:
                self.rules.mark_applied(reply.applied_rules)
            except Exception:
                pass

        self.history.append(AgentMessage("user", question))
        self.history.append(AgentMessage("assistant", reply.text))
        self.history = self.history[-self.MAX_HISTORY:]

        reply.elapsed_ms = int((time.time() - t0) * 1000)
        return reply

    # ------------------------------------------------------
    def learn(
        self, statement: str, scope: str = "general", kind: str = "procedure",
        legal_reference: str = "", taught_by: str = "নিরীক্ষক",
        supersedes: int | None = None,
    ) -> dict:
        """
        ★ নিরীক্ষকের নিশ্চিতকরণের পর নিয়মটি স্থায়ীভাবে শিখিয়া লও।
        """
        if self.rules is None:
            return {"ok": False, "error": "নিয়ম ভান্ডার সংযুক্ত নাই"}
        from knowledge.learned_rules import LearnedRule
        rid = self.rules.add(LearnedRule(
            scope=scope, kind=kind, statement=statement.strip(),
            legal_reference=legal_reference, taught_by=taught_by,
            supersedes=supersedes, source="chat",
            session_ref=self.session_ref,
        ))
        return {
            "ok": True, "rule_id": rid,
            "message": (
                f"নিয়মটি #{rid} নম্বরে সংরক্ষিত হইয়াছে এবং এখন হইতে "
                f"প্রাসঙ্গিক ক্ষেত্রে স্বয়ংক্রিয়ভাবে প্রয়োগ হইবে।"
            ),
        }

    def forget(self, rule_id: int, reason: str = "") -> dict:
        """ভুল নিয়ম প্রত্যাহার করো"""
        if self.rules is None:
            return {"ok": False, "error": "নিয়ম ভান্ডার সংযুক্ত নাই"}
        self.rules.deactivate(rule_id, reason)
        return {"ok": True, "message": f"নিয়ম #{rule_id} প্রত্যাহার করা হইল।"}

    # ------------------------------------------------------
    def _build_messages(self, question: str, rule_ctx: str) -> list[dict]:
        msgs: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if rule_ctx:
            msgs.append({"role": "system", "content": rule_ctx})
        for m in self.history[-8:]:
            if m.role in ("user", "assistant") and m.content:
                msgs.append({"role": m.role, "content": m.content})
        msgs.append({"role": "user", "content": question})
        return msgs

    # ------------------------------------------------------
    def _choose_provider(
        self, question: str, allow_cloud: bool
    ) -> tuple[Optional[LLMProvider], str]:
        """কোন স্তর ব্যবহার হইবে — গোপনীয়তা বিবেচনায়"""
        if allow_cloud and self.cloud and self.cloud.available():
            chk = check_privacy(question)
            if chk.is_safe:
                return self.cloud, "ক্লাউড স্তর ব্যবহৃত (গোপন তথ্য পাওয়া যায় নাই)"
            # গোপন তথ্য → স্থানীয়তে ফিরিয়া যাও
            if self.local.available():
                return self.local, chk.reason
            return None, chk.reason

        if self.local.available():
            return self.local, "স্থানীয় মডেল ব্যবহৃত (সম্পূর্ণ অফলাইন)"

        return None, (
            "কোনো এলএলএম পাওয়া যায় নাই। Ollama চালু আছে কিনা যাচাই করুন "
            "(টার্মিনালে: ollama serve)। আপাতত সংরক্ষিত নিয়ম হইতে উত্তর "
            "দেওয়া হইল।"
        )

    # ------------------------------------------------------
    def _fallback_answer(self, question: str, rule_ctx: str) -> str:
        """এলএলএম না থাকিলে — কেবল সংরক্ষিত নিয়ম হইতে উত্তর"""
        if rule_ctx:
            return (
                "স্থানীয় ভাষা-মডেল এই মুহূর্তে পাওয়া যায় নাই। তবে আপনার "
                "প্রশ্নের সহিত সংশ্লিষ্ট যে নিয়মসমূহ পূর্বে সংরক্ষিত হইয়াছে "
                "তাহা নিম্নরূপ:\n\n" + rule_ctx
            )
        return (
            "স্থানীয় ভাষা-মডেল পাওয়া যায় নাই এবং এই বিষয়ে পূর্বে কোনো নিয়ম "
            "সংরক্ষিত হয় নাই। অনুগ্রহ করিয়া Ollama চালু করুন অথবা প্রশ্নটি "
            "নির্দিষ্ট করিয়া পুনরায় জিজ্ঞাসা করুন।"
        )

    # ------------------------------------------------------
    def status(self) -> dict:
        """এজেন্টের অবস্থা"""
        local_ok = self.local.available()
        return {
            "স্থানীয় মডেল": {
                "অবস্থা": "চালু" if local_ok else "চালু নাই",
                "মডেল": getattr(self.local, "model", "—"),
                "RAM": f"{OllamaProvider.detect_ram_gb():.0f} GB",
                "উপলব্ধ মডেল": (
                    self.local.list_models()
                    if local_ok and hasattr(self.local, "list_models") else []
                ),
            },
            "ক্লাউড স্তর": (
                "সক্রিয়" if (self.cloud and self.cloud.available())
                else "নিষ্ক্রিয়"
            ),
            "টুল সংখ্যা": len(self.tools.tools),
            "টুলসমূহ": sorted(self.tools.tools.keys()),
            "শেখা নিয়ম": (
                self.rules.stats() if self.rules is not None else "সংযুক্ত নাই"
            ),
            "কথোপকথন": len(self.history),
        }


__all__ = [
    "AuditAgent", "AgentReply", "AgentMessage",
    "ToolRegistry", "AgentTool",
    "LLMProvider", "OllamaProvider", "CloudProvider",
    "check_privacy", "PrivacyCheck", "SYSTEM_PROMPT",
]
