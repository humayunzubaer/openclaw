"""Synthetic Bengali document benchmark for Personal Scanner.

Renders customs/VAT-style documents (forms, grid tables, letters) in several
Bengali fonts, then degrades each page three ways:

  clean  - the rendered page as-is
  scan   - flatbed-scanner look: small skew, noise, blur, JPEG
  photo  - phone-camera look: page on a background, perspective, uneven
           lighting/shadow, blur, JPEG

Everything is seeded, so the same command always produces the same set.
No real people, companies, BINs or documents are used.

Usage: python3 bench/generate.py [--out bench/generated] [--docs 6]
Needs: Pillow built with libraqm (Bengali shaping), OpenCV, NumPy.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, features

PAGE_W, PAGE_H = 1654, 2339  # A4 at 200 DPI
FONT_DIRS = [Path("/usr/share/fonts/truetype"), Path("/usr/share/fonts/opentype")]
FONT_FILES = [
    "noto/NotoSansBengali-Regular.ttf",
    "noto/NotoSerifBengali-Regular.ttf",
    "lohit-bengali/Lohit-Bengali.ttf",
    "fonts-beng-extra/Mukti.ttf",
    "fonts-beng-extra/JamrulNormal.ttf",
    "fonts-beng-extra/LikhanNormal.ttf",
]
BOLD_FALLBACK = {
    "noto/NotoSansBengali-Regular.ttf": "noto/NotoSansBengali-Bold.ttf",
    "noto/NotoSerifBengali-Regular.ttf": "noto/NotoSerifBengali-Bold.ttf",
    "fonts-beng-extra/Mukti.ttf": "fonts-beng-extra/Muktibold.ttf",
}

BN_DIGITS = "০১২৩৪৫৬৭৮৯"
# Several Bengali fonts have no Latin glyphs (they render boxes), so ASCII
# letters/digits are drawn with a Latin font, as a word processor would.
LATIN_FONT = "freefont/FreeSans.ttf"
LATIN_BOLD = "freefont/FreeSansBold.ttf"
LATIN_RUN = re.compile(r"[A-Za-z0-9]+(?:[.\-/][A-Za-z0-9]+)*\.?")

OFFICES = ["কাস্টমস বন্ড কমিশনারেট, ঢাকা", "কাস্টমস হাউস, চট্টগ্রাম", "কাস্টমস, এক্সাইজ ও ভ্যাট কমিশনারেট, ঢাকা (দক্ষিণ)",
           "বৃহৎ করদাতা ইউনিট (মূসক)", "কাস্টমস বন্ড কমিশনারেট, চট্টগ্রাম"]
TITLES = ["কর চালানপত্র", "মাসিক রাজস্ব বিবরণী", "বন্ড নিরীক্ষা প্রতিবেদন", "কাঁচামাল প্রাপ্তি ও ব্যবহারের হিসাব",
          "আমদানি প্রাপ্যতা বিবরণী", "পণ্য সরবরাহের চালান"]
LABELS = [
    ("নিবন্ধিত ব্যক্তির নাম", "company"), ("ঠিকানা", "address"), ("বিআইএন", "bin"), ("চালানপত্র নম্বর", "ref"),
    ("ইস্যুর তারিখ", "date"), ("বন্ড লাইসেন্স নম্বর", "ref"), ("ইউডি নম্বর", "ref"), ("এলসি নম্বর", "lc"),
    ("যানবাহনের প্রকৃতি ও নম্বর", "vehicle"), ("মোট মূল্য (টাকা)", "amount"), ("মোবাইল নম্বর", "phone"),
    ("প্রাপকের নাম", "company"), ("এইচএস কোড", "hs"), ("পরিমাণ", "qty"),
]
COMPANY_A = ["মেঘনা", "পদ্মা", "যমুনা", "সোনালী", "রূপালী", "সবুজ", "নবারুণ", "প্রগতি", "আলফা", "দিগন্ত"]
COMPANY_B = ["টেক্সটাইল মিলস লিমিটেড", "গার্মেন্টস লিমিটেড", "প্যাকেজিং ইন্ডাস্ট্রিজ", "অ্যাপারেলস লিমিটেড",
             "নিটওয়্যার লিমিটেড", "এক্সেসরিজ লিমিটেড", "ডায়িং মিলস লিমিটেড"]
PLACES = ["আশুলিয়া, সাভার, ঢাকা", "টঙ্গী, গাজীপুর", "নারায়ণগঞ্জ", "ফতুল্লা, নারায়ণগঞ্জ", "কালুরঘাট, চট্টগ্রাম",
          "উত্তরা ইপিজেড, নীলফামারী", "মিরপুর, ঢাকা"]
MONTHS = ["জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন", "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর",
          "নভেম্বর", "ডিসেম্বর"]
GOODS = ["সুতি কাপড়", "পলিয়েস্টার সুতা", "বোতাম", "জিপার", "কার্টন", "লেবেল", "রং ও রাসায়নিক", "ইলাস্টিক",
         "প্লাস্টিক ব্যাগ", "টুইল ফেব্রিক", "ডেনিম কাপড়", "সেলাই সুতা", "হ্যাঙ্গার", "পলি ব্যাগ"]
UNITS = ["কেজি", "মিটার", "পিস", "গজ", "ডজন", "লিটার"]
REMARKS = ["পরিশোধিত", "যাচাইকৃত", "বকেয়া", "সমন্বিত", "প্রযোজ্য নয়", "হিসাবভুক্ত"]
SENTENCES = [
    "বন্ডেড প্রতিষ্ঠানটির কাঁচামাল আমদানি ও ব্যবহারের হিসাব নিরীক্ষা করা হয়েছে।",
    "আমদানিকৃত কাঁচামালের প্রাপ্যতা ইউডি অনুযায়ী যাচাই করে দেখা গেছে।",
    "প্রতিষ্ঠানের মজুদ রেজিস্টারে কিছু অসংগতি পরিলক্ষিত হয়েছে।",
    "মূল্য সংযোজন কর যথাসময়ে পরিশোধ করা হয়েছে মর্মে প্রত্যয়ন করা যাচ্ছে।",
    "রপ্তানি ঋণপত্রের বিপরীতে ব্যাক টু ব্যাক ঋণপত্র খোলা হয়েছে।",
    "উল্লিখিত পণ্যের এইচএস কোড ও শুল্কহার সঠিকভাবে প্রয়োগ করা হয়েছে।",
    "নিরীক্ষাকালীন সময়ে প্রতিষ্ঠানের প্রতিনিধি উপস্থিত ছিলেন।",
    "বন্ড লাইসেন্সের মেয়াদ নবায়নের জন্য প্রয়োজনীয় কাগজপত্র দাখিল করা হয়েছে।",
    "সহগ অনুযায়ী কাঁচামালের প্রকৃত ব্যবহার নির্ধারণ করা হয়েছে।",
    "অব্যবহৃত কাঁচামালের উপর প্রযোজ্য শুল্ক-কর আদায়যোগ্য।",
    "প্রাপ্ত তথ্যাদি পর্যালোচনা করে নিম্নরূপ মতামত প্রদান করা হলো।",
    "বিষয়টি পরবর্তী প্রয়োজনীয় ব্যবস্থা গ্রহণের জন্য উপস্থাপন করা হলো।",
    "Invoice No. এবং LC No. যথাযথভাবে উল্লেখ করা হয়েছে।",
    "Bill of Entry অনুযায়ী পণ্য খালাস সম্পন্ন হয়েছে।",
    "সংশ্লিষ্ট সকল দলিলাদির সত্যায়িত কপি সংযুক্ত করা হলো।",
    "ঘোষণা: আমি প্রদত্ত তথ্য সঠিক বলে ঘোষণা করছি।",
]


def bn(n: int | str) -> str:
    return "".join(BN_DIGITS[int(c)] if c.isdigit() else c for c in str(n))


def money(rng: random.Random) -> str:
    return bn(f"{rng.randint(1, 999)},{rng.randint(0, 999):03d}")


def value_for(kind: str, rng: random.Random) -> str:
    if kind == "company":
        return f"{rng.choice(COMPANY_A)} {rng.choice(COMPANY_B)}"
    if kind == "address":
        return rng.choice(PLACES)
    if kind == "bin":
        return bn("".join(str(rng.randint(0, 9)) for _ in range(9)) + "-" + f"{rng.randint(0, 9999):04d}")
    if kind == "ref":
        return bn(f"{rng.randint(100, 999)}/{rng.randint(10, 99)}/{rng.randint(2023, 2026)}")
    if kind == "lc":
        return f"LC-{rng.randint(1000, 9999)}{rng.randint(10, 99)}"
    if kind == "date":
        return bn(f"{rng.randint(1, 28):02d}") + f" {rng.choice(MONTHS)} " + bn(rng.randint(2023, 2026))
    if kind == "vehicle":
        return "ট্রাক, ঢাকা মেট্রো-ট " + bn(f"{rng.randint(11, 99)}-{rng.randint(1000, 9999)}")
    if kind == "amount":
        return money(rng)
    if kind == "phone":
        return bn(f"01{rng.randint(3, 9)}{rng.randint(10, 99)}-{rng.randint(100000, 999999)}")
    if kind == "hs":
        return bn(f"{rng.randint(1000, 9999)}.{rng.randint(10, 99)}.{rng.randint(10, 99)}")
    if kind == "qty":
        return bn(rng.randint(10, 9999)) + " " + rng.choice(UNITS)
    raise ValueError(kind)


def font_path(rel: str) -> str:
    for d in FONT_DIRS:
        p = d / rel
        if p.exists():
            return str(p)
    raise FileNotFoundError(rel)


class Page:
    def __init__(self, font_rel: str, rng: random.Random):
        self.img = Image.new("L", (PAGE_W, PAGE_H), 255)
        self.draw = ImageDraw.Draw(self.img)
        self.font_rel = font_rel
        self.bold_rel = BOLD_FALLBACK.get(font_rel, font_rel)
        self.rng = rng
        self.lines: list[str] = []

    def font(self, size: int, bold: bool = False):
        return ImageFont.truetype(font_path(self.bold_rel if bold else self.font_rel), size, layout_engine=ImageFont.Layout.RAQM)

    def latin_font(self, size: int, bold: bool = False):
        return ImageFont.truetype(font_path(LATIN_BOLD if bold else LATIN_FONT), size)

    def runs(self, s: str, size: int, bold: bool):
        pos = 0
        for m in LATIN_RUN.finditer(s):
            if m.start() > pos:
                yield s[pos:m.start()], self.font(size, bold)
            yield m.group(), self.latin_font(size, bold)
            pos = m.end()
        if pos < len(s):
            yield s[pos:], self.font(size, bold)

    def text(self, xy, s: str, size: int, bold: bool = False, record: bool = True):
        x, y = xy
        for run, font in self.runs(s, size, bold):
            self.draw.text((x, y), run, fill=15, font=font)
            x += self.draw.textlength(run, font=font)
        if record:
            self.lines.append(s)

    def text_width(self, s: str, size: int) -> float:
        return sum(self.draw.textlength(r, font=f) for r, f in self.runs(s, size, False))

    def header(self, title: str):
        self.text((110, 110), "গণপ্রজাতন্ত্রী বাংলাদেশ সরকার", 40, bold=True)
        self.text((110, 180), self.rng.choice(OFFICES), 32)
        self.text((110, 250), title, 36, bold=True)
        self.draw.line((110, 320, PAGE_W - 110, 320), fill=20, width=3)


def layout_form(page: Page):
    rng = page.rng
    page.header(rng.choice(TITLES))
    size = rng.choice([28, 30, 32])
    y = 380
    for label, kind in rng.sample(LABELS, 8):
        value = value_for(kind, rng)
        page.draw.rectangle((110, y, PAGE_W - 110, y + 110), outline=60, width=2)
        page.draw.line((560, y, 560, y + 110), fill=60, width=2)
        page.text((135, y + 30), label, size, bold=True, record=False)
        page.text((590, y + 30), value, size, record=False)
        page.lines.append(f"{label} {value}")
        y += 135
    y += 60
    page.text((115, y), SENTENCES[-1], size)
    page.text((115, y + 80), "তারিখ: " + value_for("date", rng), size)


def layout_table(page: Page):
    rng = page.rng
    page.header(rng.choice(TITLES))
    size = rng.choice([26, 28, 30])
    headers = ["ক্রম", "পণ্যের বিবরণ", "পরিমাণ", "একক মূল্য", "মোট মূল্য", "মন্তব্য"]
    widths = [110, 390, 230, 220, 250, 234]
    rows = []
    for i in range(rng.randint(6, 9)):
        rows.append([bn(i + 1), rng.choice(GOODS), bn(rng.randint(10, 9999)) + " " + rng.choice(UNITS),
                     bn(rng.randint(10, 999)), money(rng), rng.choice(REMARKS)])
    rows.append(["", "মোট", "", "", money(rng), ""])
    x0, y0, rh = 110, 380, 92
    for r, row in enumerate([headers] + rows):
        x = x0
        y = y0 + r * rh
        for w, cell in zip(widths, row):
            page.draw.rectangle((x, y, x + w, y + rh), outline=40, width=2)
            if cell:
                page.text((x + 14, y + 26), cell, size, bold=(r == 0 or r == len(rows)), record=False)
            x += w
        page.lines.append(" ".join(c for c in row if c))
    y = y0 + (len(rows) + 1) * rh + 70
    page.text((115, y), rng.choice(SENTENCES[:-1]), size)


def layout_letter(page: Page):
    rng = page.rng
    page.header(rng.choice(TITLES))
    size = rng.choice([28, 30, 32])
    page.text((110, 370), "স্মারক নং: " + value_for("ref", rng) + "    তারিখ: " + value_for("date", rng), size)
    page.text((110, 440), "বিষয়: " + f"{rng.choice(COMPANY_A)} {rng.choice(COMPANY_B)}" + "-এর বন্ড নিরীক্ষা", size, bold=True)
    y = 540
    max_w = PAGE_W - 240
    for sentence in rng.sample(SENTENCES[:-1], 7):
        words, line = sentence.split(), ""
        for w in words:
            trial = (line + " " + w).strip()
            if page.text_width(trial, size) > max_w and line:
                page.text((120, y), line, size)
                y += int(size * 1.9)
                line = w
            else:
                line = trial
        if line:
            page.text((120, y), line, size)
            y += int(size * 1.9)
        y += int(size * 0.6)
    page.text((1000, y + 80), "স্বাক্ষরিত", size, record=True)
    page.text((1000, y + 150), "সহকারী রাজস্ব কর্মকর্তা", size)


LAYOUTS = {"form": layout_form, "table": layout_table, "letter": layout_letter}


def degrade_scan(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    h, w = img.shape
    angle = rng.uniform(-1.5, 1.5)
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    out = cv2.warpAffine(img, m, (w, h), borderValue=255)
    out = cv2.GaussianBlur(out, (3, 3), 0.6)
    out = np.clip(out.astype(np.float32) + rng.normal(0, 6, out.shape), 0, 255).astype(np.uint8)
    return jpeg(out, 75)


def degrade_photo(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    h, w = img.shape
    canvas_w, canvas_h = int(w * 1.25), int(h * 1.2)
    bg = np.full((canvas_h, canvas_w, 3), rng.integers(40, 90, 3), np.uint8)
    bg = np.clip(bg.astype(np.int16) + rng.integers(-12, 12, bg.shape), 0, 255).astype(np.uint8)
    page = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR).astype(np.float32)
    page *= np.array([0.93, 0.97, 1.0], np.float32)  # warm paper tint (BGR)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    ox, oy = (canvas_w - w) / 2, (canvas_h - h) / 2
    j = 0.05
    dst = np.float32([[ox + rng.uniform(-j, j) * w, oy + rng.uniform(-j, j) * h] if i == 0 else
                      [ox + w + rng.uniform(-j, j) * w, oy + rng.uniform(-j, j) * h] if i == 1 else
                      [ox + w + rng.uniform(-j, j) * w, oy + h + rng.uniform(-j, j) * h] if i == 2 else
                      [ox + rng.uniform(-j, j) * w, oy + h + rng.uniform(-j, j) * h] for i in range(4)])
    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(page, m, (canvas_w, canvas_h), borderValue=(0, 0, 0))
    mask = cv2.warpPerspective(np.ones((h, w), np.float32), m, (canvas_w, canvas_h))
    out = warped * mask[..., None] + bg.astype(np.float32) * (1 - mask[..., None])
    # uneven light: linear gradient + soft shadow blob
    yy, xx = np.mgrid[0:canvas_h, 0:canvas_w].astype(np.float32)
    ang = rng.uniform(0, 2 * np.pi)
    grad = (np.cos(ang) * xx / canvas_w + np.sin(ang) * yy / canvas_h)
    grad = (grad - grad.min()) / (grad.max() - grad.min() + 1e-6)
    light = 1.0 - rng.uniform(0.25, 0.45) * grad
    cx, cy = rng.uniform(0.2, 0.8) * canvas_w, rng.uniform(0.2, 0.8) * canvas_h
    r = rng.uniform(0.25, 0.4) * canvas_w
    blob = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)))
    light *= 1.0 - rng.uniform(0.15, 0.3) * blob
    out *= light[..., None]
    out = cv2.GaussianBlur(out, (0, 0), rng.uniform(0.8, 1.3))
    out = np.clip(out + rng.normal(0, 5, out.shape), 0, 255).astype(np.uint8)
    scale = 2000 / canvas_w
    out = cv2.resize(out, (2000, int(canvas_h * scale)), interpolation=cv2.INTER_AREA)
    return jpeg(out, 82)


def jpeg(img: np.ndarray, q: int) -> np.ndarray:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    assert ok
    return cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).parent / "generated"))
    ap.add_argument("--docs", type=int, default=6, help="documents per layout")
    ap.add_argument("--seed", type=int, default=20260926)
    args = ap.parse_args()
    if not features.check("raqm"):
        raise SystemExit("Pillow lacks libraqm: Bengali would render with broken shaping. Install libraqm0.")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cases = []
    for layout_name, fn in LAYOUTS.items():
        for i in range(args.docs):
            seed = args.seed + hash_str(layout_name) + i
            rng = random.Random(seed)
            font_rel = FONT_FILES[(i + len(layout_name)) % len(FONT_FILES)]
            page = Page(font_rel, rng)
            fn(page)
            clean = np.array(page.img)
            nrng = np.random.default_rng(seed)
            base = f"{layout_name}-{i + 1:02d}"
            variants = {"clean": clean, "scan": degrade_scan(clean, nrng), "photo": degrade_photo(clean, nrng)}
            for deg, img in variants.items():
                name = f"{base}-{deg}.{'png' if deg == 'clean' else 'jpg'}"
                cv2.imwrite(str(out / name), img)
                cases.append({"id": f"{base}-{deg}", "image": name, "category": layout_name, "degradation": deg,
                              "font": Path(font_rel).stem, "expectedText": "\n".join(page.lines)})
    manifest = {"schemaVersion": 1, "generator": "bench/generate.py", "seed": args.seed,
                "privacy": "Synthetic; no real people, companies or documents.", "cases": cases}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(cases)} cases to {out}")


def hash_str(s: str) -> int:
    return sum(ord(c) * (i + 1) for i, c in enumerate(s))


if __name__ == "__main__":
    main()
