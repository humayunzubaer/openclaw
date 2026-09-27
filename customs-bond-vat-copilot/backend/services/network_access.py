"""
Network Access — LAN ও Tailscale অ্যাক্সেস ব্যবস্থাপনা
========================================================

নীতি:
    নিরীক্ষার তথ্য সরকারি ও গোপনীয়। কোনো তৃতীয় পক্ষের সার্ভারে
    তথ্য যাইবে না। সফটওয়্যার নিরীক্ষকের নিজস্ব যন্ত্রেই চলিবে;
    ফোন বা অন্য যন্ত্র সরাসরি ঐ যন্ত্রের সহিত যুক্ত হইবে।

তিনটি অ্যাক্সেস স্তর:

    ১) LOCAL     — কেবল ঐ যন্ত্রে (127.0.0.1)
                   সর্বোচ্চ নিরাপদ, ইন্টারনেট লাগে না

    ২) LAN       — একই ওয়াই-ফাই নেটওয়ার্কে (192.168.x.x)
                   অফিস/বাসায় ফোন হইতে ব্যবহার; ইন্টারনেট লাগে না

    ৩) TAILSCALE — ব্যক্তিগত এনক্রিপ্টেড মেশ (100.x.y.z)
                   যেকোনো স্থান হইতে; ট্রাফিক peer-to-peer ও
                   প্রান্ত-হইতে-প্রান্ত এনক্রিপ্টেড

নিরাপত্তা ব্যবস্থা:
    • প্রতিটি স্তরে পৃথক অনুমোদন
    • ডিভাইস জোড়া লাগাইতে এককালীন PIN
    • অনুমোদিত IP পরিসর ছাড়া সংযোগ প্রত্যাখ্যান
    • সকল সংযোগ লিপিবদ্ধ (audit trail)
    • কোনো অবস্থাতেই পাবলিক ইন্টারনেটে উন্মুক্ত নহে
"""

from __future__ import annotations

import ipaddress
import json
import platform
import secrets
import socket
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

from utils.logger import logger


# ==========================================================
# অ্যাক্সেস স্তর
# ==========================================================

class AccessMode(str, Enum):
    LOCAL = "local"           # কেবল এই যন্ত্র
    LAN = "lan"               # একই ওয়াই-ফাই
    TAILSCALE = "tailscale"   # ব্যক্তিগত মেশ
    LAN_TAILSCALE = "lan_tailscale"   # উভয়


# বিশ্বাসযোগ্য IP পরিসর
PRIVATE_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),      # লোকালহোস্ট
    ipaddress.ip_network("10.0.0.0/8"),       # ব্যক্তিগত
    ipaddress.ip_network("172.16.0.0/12"),    # ব্যক্তিগত
    ipaddress.ip_network("192.168.0.0/16"),   # গৃহ/অফিস ওয়াই-ফাই
    ipaddress.ip_network("169.254.0.0/16"),   # লিংক-লোকাল
]

# Tailscale এর নির্দিষ্ট পরিসর (CGNAT)
TAILSCALE_RANGE = ipaddress.ip_network("100.64.0.0/10")

DEFAULT_PORT = 8765


# ==========================================================
# নেটওয়ার্ক শনাক্তকরণ
# ==========================================================

@dataclass
class NetworkInfo:
    """যন্ত্রের নেটওয়ার্ক অবস্থা"""
    hostname: str = ""
    local_ip: str = "127.0.0.1"
    lan_ip: str = ""
    tailscale_ip: str = ""
    tailscale_running: bool = False
    tailscale_hostname: str = ""
    platform_name: str = ""

    @property
    def lan_url(self) -> str:
        return f"http://{self.lan_ip}:{DEFAULT_PORT}" if self.lan_ip else ""

    @property
    def tailscale_url(self) -> str:
        return (
            f"http://{self.tailscale_ip}:{DEFAULT_PORT}"
            if self.tailscale_ip else ""
        )

    @property
    def local_url(self) -> str:
        return f"http://127.0.0.1:{DEFAULT_PORT}"


def _detect_lan_ip() -> str:
    """এই যন্ত্রের ওয়াই-ফাই/ল্যান আইপি বাহির করো"""
    try:
        # বাহিরের দিকে সংযোগের চেষ্টা করিয়া নিজের আইপি জানা যায়
        # (প্রকৃত তথ্য পাঠানো হয় না)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return ""


def _detect_tailscale() -> tuple[bool, str, str]:
    """
    Tailscale চালু আছে কিনা ও তাহার আইপি নির্ণয় করো।
    ফেরত: (চালু?, আইপি, হোস্টনাম)
    """
    candidates = [
        "tailscale",
        "/usr/bin/tailscale",
        "/usr/local/bin/tailscale",
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
        r"C:\Program Files\Tailscale\tailscale.exe",
    ]
    for exe in candidates:
        try:
            out = subprocess.run(
                [exe, "status", "--json"],
                capture_output=True, text=True, timeout=4,
            )
            if out.returncode != 0 or not out.stdout.strip():
                continue
            data = json.loads(out.stdout)
            self_node = data.get("Self") or {}
            ips = self_node.get("TailscaleIPs") or []
            v4 = next((i for i in ips if ":" not in i), "")
            host = (self_node.get("DNSName") or "").rstrip(".")
            running = str(data.get("BackendState", "")).lower() == "running"
            return running, v4, host
        except (FileNotFoundError, subprocess.TimeoutExpired,
                json.JSONDecodeError, OSError):
            continue
    return False, "", ""


def detect_network() -> NetworkInfo:
    """যন্ত্রের সম্পূর্ণ নেটওয়ার্ক অবস্থা"""
    info = NetworkInfo(platform_name=platform.system())
    try:
        info.hostname = socket.gethostname()
    except Exception:
        info.hostname = "unknown"

    info.lan_ip = _detect_lan_ip()
    running, ts_ip, ts_host = _detect_tailscale()
    info.tailscale_running = running
    info.tailscale_ip = ts_ip
    info.tailscale_hostname = ts_host
    return info


# ==========================================================
# ডিভাইস জোড়া লাগানো (Pairing)
# ==========================================================

@dataclass
class PairedDevice:
    """অনুমোদিত একটি যন্ত্র"""
    device_id: str
    name: str
    ip: str
    mode: str                    # lan | tailscale
    paired_at: str
    last_seen: str = ""
    is_active: bool = True
    note: str = ""


@dataclass
class PairingSession:
    """চলমান জোড়া-লাগানোর সেশন — এককালীন PIN"""
    pin: str
    expires_at: datetime
    used: bool = False

    @property
    def is_valid(self) -> bool:
        return not self.used and datetime.now() < self.expires_at

    @property
    def seconds_left(self) -> int:
        return max(0, int((self.expires_at - datetime.now()).total_seconds()))


# ==========================================================
# অ্যাক্সেস নিয়ন্ত্রক
# ==========================================================

class NetworkAccessManager:
    """
    কোন যন্ত্র কোন পথে সংযোগ করিতে পারিবে তাহা নিয়ন্ত্রণ করে।

    ব্যবহার:
        nm = NetworkAccessManager(config_path)
        nm.set_mode(AccessMode.LAN_TAILSCALE)
        pin = nm.start_pairing()          # ফোনে এই PIN দিতে হইবে
        nm.complete_pairing(pin, ip, "আমার ফোন")
    """

    PAIRING_TTL_SECONDS = 300     # PIN ৫ মিনিট বৈধ

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.mode: AccessMode = AccessMode.LOCAL
        self.devices: dict[str, PairedDevice] = {}
        self.access_log: list[dict] = []
        self._pairing: Optional[PairingSession] = None
        self.network = detect_network()
        self._load()

    # ------------------------------------------------------
    def _load(self):
        if not self.config_path.exists():
            return
        try:
            d = json.loads(self.config_path.read_text(encoding="utf-8"))
            self.mode = AccessMode(d.get("mode", "local"))
            self.devices = {
                k: PairedDevice(**v) for k, v in (d.get("devices") or {}).items()
            }
            self.access_log = d.get("access_log", [])[-500:]
        except Exception as e:
            logger.warning(f"নেটওয়ার্ক কনফিগ পড়া যায় নাই: {e}")

    def _save(self):
        self.config_path.write_text(
            json.dumps({
                "mode": self.mode.value,
                "devices": {k: asdict(v) for k, v in self.devices.items()},
                "access_log": self.access_log[-500:],
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------
    def set_mode(self, mode: AccessMode) -> dict:
        """অ্যাক্সেস স্তর নির্ধারণ করো"""
        self.mode = mode
        self._save()

        self.network = detect_network()
        urls = self.get_access_urls()

        logger.info(f"অ্যাক্সেস স্তর নির্ধারিত: {mode.value}")
        if mode in (AccessMode.TAILSCALE, AccessMode.LAN_TAILSCALE):
            if not self.network.tailscale_running:
                logger.warning(
                    "⚠ Tailscale চালু পাওয়া যায় নাই — "
                    "অ্যাপটি ইনস্টল ও লগইন করা আছে কিনা যাচাই করুন"
                )
        return {"mode": mode.value, "urls": urls}

    # ------------------------------------------------------
    def bind_host(self) -> str:
        """FastAPI কোন ঠিকানায় শুনিবে"""
        if self.mode == AccessMode.LOCAL:
            return "127.0.0.1"
        return "0.0.0.0"      # LAN ও Tailscale উভয় ইন্টারফেসে

    # ------------------------------------------------------
    def get_access_urls(self) -> dict:
        """ফোনে দেখানোর জন্য সংযোগের ঠিকানা"""
        n = self.network
        out = {"local": n.local_url}
        if self.mode in (AccessMode.LAN, AccessMode.LAN_TAILSCALE):
            out["lan"] = n.lan_url
        if self.mode in (AccessMode.TAILSCALE, AccessMode.LAN_TAILSCALE):
            out["tailscale"] = n.tailscale_url
            if n.tailscale_hostname:
                out["tailscale_name"] = (
                    f"http://{n.tailscale_hostname}:{DEFAULT_PORT}"
                )
        return {k: v for k, v in out.items() if v}

    # ------------------------------------------------------
    def classify_ip(self, ip: str) -> str:
        """আইপি কোন শ্রেণীর — local | lan | tailscale | public"""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return "invalid"
        if addr.is_loopback:
            return "local"
        if addr in TAILSCALE_RANGE:
            return "tailscale"
        for net in PRIVATE_RANGES:
            if addr in net:
                return "lan"
        return "public"

    # ------------------------------------------------------
    def is_allowed(self, ip: str) -> tuple[bool, str]:
        """
        এই আইপি হইতে সংযোগ অনুমোদিত কিনা।
        ফেরত: (অনুমোদিত?, কারণ)
        """
        kind = self.classify_ip(ip)

        if kind == "invalid":
            return False, "অবৈধ আইপি ঠিকানা"

        # ★ পাবলিক ইন্টারনেট কখনোই নহে
        if kind == "public":
            self._log(ip, kind, False, "পাবলিক আইপি — সর্বদা প্রত্যাখ্যাত")
            return False, (
                "পাবলিক ইন্টারনেট হইতে সংযোগ অনুমোদিত নহে। "
                "নিরীক্ষার তথ্য সুরক্ষার স্বার্থে কেবল স্থানীয় নেটওয়ার্ক "
                "অথবা Tailscale মেশ হইতে সংযোগ গ্রহণ করা হয়।"
            )

        if kind == "local":
            return True, "স্থানীয় যন্ত্র"

        if kind == "lan":
            if self.mode in (AccessMode.LAN, AccessMode.LAN_TAILSCALE):
                ok = self._device_check(ip, "lan")
                return ok, ("অনুমোদিত যন্ত্র (LAN)" if ok
                            else "যন্ত্রটি জোড়া লাগানো নাই — PIN দিয়া যুক্ত করুন")
            return False, "LAN অ্যাক্সেস বন্ধ আছে — সেটিংসে চালু করুন"

        if kind == "tailscale":
            if self.mode in (AccessMode.TAILSCALE, AccessMode.LAN_TAILSCALE):
                ok = self._device_check(ip, "tailscale")
                return ok, ("অনুমোদিত যন্ত্র (Tailscale)" if ok
                            else "যন্ত্রটি জোড়া লাগানো নাই — PIN দিয়া যুক্ত করুন")
            return False, "Tailscale অ্যাক্সেস বন্ধ আছে — সেটিংসে চালু করুন"

        return False, "অজ্ঞাত নেটওয়ার্ক"

    def _device_check(self, ip: str, kind: str) -> bool:
        dev = next(
            (d for d in self.devices.values() if d.ip == ip and d.is_active),
            None,
        )
        if dev:
            dev.last_seen = datetime.now().isoformat(timespec="seconds")
            self._save()
            self._log(ip, kind, True, f"অনুমোদিত: {dev.name}")
            return True
        self._log(ip, kind, False, "অনিবন্ধিত যন্ত্র")
        return False

    # ------------------------------------------------------
    def start_pairing(self) -> PairingSession:
        """
        নূতন যন্ত্র যুক্ত করিতে এককালীন PIN তৈরি করো।
        ডেস্কটপ পর্দায় PIN দেখাইবে; ফোনে উহা প্রবেশ করাইতে হইবে।
        """
        pin = f"{secrets.randbelow(1_000_000):06d}"
        self._pairing = PairingSession(
            pin=pin,
            expires_at=datetime.now() + timedelta(seconds=self.PAIRING_TTL_SECONDS),
        )
        logger.info(f"যন্ত্র সংযোজনের PIN তৈরি হইল (৫ মিনিট বৈধ)")
        return self._pairing

    def complete_pairing(
        self, pin: str, ip: str, device_name: str = ""
    ) -> tuple[bool, str]:
        """PIN যাচাই করিয়া যন্ত্র নিবন্ধন করো"""
        s = self._pairing
        if not s or not s.is_valid:
            return False, "PIN এর মেয়াদ শেষ — নূতন PIN তৈরি করুন"
        if not secrets.compare_digest(str(pin), s.pin):
            return False, "PIN মেলে নাই"

        kind = self.classify_ip(ip)
        if kind == "public":
            return False, "পাবলিক আইপি হইতে যন্ত্র যুক্ত করা যাইবে না"

        did = secrets.token_hex(8)
        self.devices[did] = PairedDevice(
            device_id=did,
            name=device_name or f"যন্ত্র-{len(self.devices) + 1}",
            ip=ip, mode=kind,
            paired_at=datetime.now().isoformat(timespec="seconds"),
        )
        s.used = True
        self._save()
        logger.success(f"যন্ত্র যুক্ত হইল: {device_name} ({ip}, {kind})")
        return True, f"'{device_name}' সফলভাবে যুক্ত হইয়াছে"

    def remove_device(self, device_id: str) -> bool:
        if device_id in self.devices:
            name = self.devices[device_id].name
            del self.devices[device_id]
            self._save()
            logger.info(f"যন্ত্র অপসারিত: {name}")
            return True
        return False

    # ------------------------------------------------------
    def _log(self, ip: str, kind: str, allowed: bool, reason: str):
        self.access_log.append({
            "সময়": datetime.now().isoformat(timespec="seconds"),
            "আইপি": ip, "ধরন": kind,
            "অনুমোদিত": allowed, "কারণ": reason,
        })
        if len(self.access_log) > 1000:
            self.access_log = self.access_log[-500:]

    # ------------------------------------------------------
    def status(self) -> dict:
        """সেটিংস পর্দায় দেখানোর জন্য"""
        n = self.network
        return {
            "অ্যাক্সেস স্তর": {
                AccessMode.LOCAL: "কেবল এই যন্ত্র",
                AccessMode.LAN: "একই ওয়াই-ফাই (LAN)",
                AccessMode.TAILSCALE: "Tailscale মেশ",
                AccessMode.LAN_TAILSCALE: "LAN + Tailscale",
            }[self.mode],
            "যন্ত্রের নাম": n.hostname,
            "প্ল্যাটফর্ম": n.platform_name,
            "সংযোগের ঠিকানা": self.get_access_urls(),
            "Tailscale": (
                f"চালু — {n.tailscale_ip}" if n.tailscale_running
                else "চালু নাই"
            ),
            "যুক্ত যন্ত্র": [
                {
                    "নাম": d.name, "আইপি": d.ip, "ধরন": d.mode,
                    "যুক্ত হইয়াছে": d.paired_at,
                    "সর্বশেষ": d.last_seen or "—",
                }
                for d in self.devices.values() if d.is_active
            ],
            "সাম্প্রতিক সংযোগ প্রচেষ্টা": self.access_log[-10:],
            "নিরাপত্তা নোট": (
                "পাবলিক ইন্টারনেট হইতে সংযোগ সর্বাবস্থায় প্রত্যাখ্যাত। "
                "নিরীক্ষার কোনো তথ্য তৃতীয় পক্ষের সার্ভারে প্রেরিত হয় না।"
            ),
        }


# ==========================================================
# Tailscale সহায়িকা
# ==========================================================

TAILSCALE_SETUP_GUIDE = {
    "title": "Tailscale সংযোগ প্রস্তুতি",
    "why": (
        "Tailscale আপনার ল্যাপটপ ও ফোনের মধ্যে একটি ব্যক্তিগত এনক্রিপ্টেড "
        "সুড়ঙ্গ তৈরি করে। তথ্য সরাসরি দুই যন্ত্রের মধ্যে যাতায়াত করে — "
        "কোনো তৃতীয় পক্ষ উহা পড়িতে পারে না। ফলে অফিসের বাহিরে থাকিয়াও "
        "নিরাপদে সফটওয়্যার ব্যবহার করা যায়।"
    ),
    "steps": [
        "১। ল্যাপটপে tailscale.com হইতে Tailscale ইনস্টল করুন "
        "(ম্যাকে .pkg, উইন্ডোজে .msi)",
        "২। একটি ব্যক্তিগত ইমেইল দিয়া লগইন করুন — Personal প্ল্যান বিনামূল্যে",
        "৩। ফোনেও একই অ্যাকাউন্টে Tailscale অ্যাপ ইনস্টল ও লগইন করুন",
        "৪। এই সফটওয়্যারের সেটিংসে গিয়া অ্যাক্সেস স্তর 'LAN + Tailscale' করুন",
        "৫। 'নূতন যন্ত্র যুক্ত করুন' চাপিয়া PIN নিন",
        "৬। ফোনের ব্রাউজারে Tailscale ঠিকানা খুলিয়া PIN দিন",
    ],
    "notes": [
        "ল্যাপটপ চালু ও Tailscale সংযুক্ত থাকিতে হইবে",
        "উভয় যন্ত্রে ইন্টারনেট লাগিবে (কেবল সংযোগ স্থাপনের জন্য)",
        "একই ওয়াই-ফাইতে থাকিলে Tailscale ছাড়াই LAN ঠিকানা কাজ করিবে",
    ],
}


__all__ = [
    "AccessMode", "NetworkInfo", "detect_network",
    "PairedDevice", "PairingSession", "NetworkAccessManager",
    "TAILSCALE_SETUP_GUIDE", "DEFAULT_PORT",
]
