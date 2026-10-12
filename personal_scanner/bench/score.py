"""Score an OCR engine against a benchmark manifest.

Metrics per case (same definitions as the Manus scorer in lib/ocr-benchmark.ts,
plus a numeric metric that matters most for audit work):

  char_acc   1 - CER over non-whitespace characters (NFC-normalized)
  word_acc   1 - word-level edit distance / expected words
  num_acc    share of expected numeric tokens (BIN, amounts, dates, qty)
             reproduced exactly, as a multiset match

Engines:
  raw  - stock `tesseract -l ben --psm 3`, the baseline
  ps   - Personal Scanner core (`build/ps_ocr <image>`)

Usage:
  python3 bench/score.py --engine ps --manifest bench/generated/manifest.json
  python3 bench/score.py --engine raw --manifest bench/reference/manifest.json --show
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUMERIC = re.compile(r"[0-9০-৯]")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[​-‍﻿]", "", text)
    text = re.sub(r"_{3,}", " ", text)  # signature rules are not text
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\r?\n+", "\n", text)
    return text.strip()


def levenshtein(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            cur[j] = prev[j - 1] if ai == b[j - 1] else 1 + min(prev[j - 1], cur[j - 1], prev[j])
        prev = cur
    return prev[len(b)]


def numeric_tokens(text: str) -> Counter:
    return Counter(t.strip(".,:;()") for t in text.split() if NUMERIC.search(t))


def score_case(expected: str, actual: str) -> dict:
    e, a = normalize(expected), normalize(actual)
    ec, ac = list(re.sub(r"\s", "", e)), list(re.sub(r"\s", "", a))
    ew, aw = e.split(), a.split()
    en, an = numeric_tokens(e), numeric_tokens(a)
    matched = sum((en & an).values())
    return {
        "char_acc": max(0.0, 1 - levenshtein(ec, ac) / len(ec)) if ec else 1.0,
        "word_acc": max(0.0, 1 - levenshtein(ew, aw) / len(ew)) if ew else 1.0,
        "num_acc": matched / sum(en.values()) if en else 1.0,
    }


def run_engine(engine: str, image: Path, binary: Path) -> str:
    if engine == "raw":
        cmd = ["tesseract", str(image), "-", "-l", "ben", "--psm", "3"]
    else:
        cmd = [str(binary), str(image)]
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    res = subprocess.run(cmd, capture_output=True, env=env, timeout=600)
    if res.returncode != 0:
        sys.stderr.write(f"[{image.name}] exit {res.returncode}: {res.stderr.decode(errors='replace')[-400:]}\n")
    return res.stdout.decode("utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["raw", "ps"], default="ps")
    ap.add_argument("--manifest", default=str(ROOT / "bench/generated/manifest.json"))
    ap.add_argument("--binary", default=str(ROOT / "build/ps_ocr"))
    ap.add_argument("--filter", default="", help="regex on case id")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--show", action="store_true", help="print OCR text of each case")
    ap.add_argument("--json", help="write per-case results here")
    ap.add_argument("--min-char", type=float, help="fail (exit 1) if overall char_acc is below this")
    ap.add_argument("--min-num", type=float, help="fail (exit 1) if overall num_acc is below this")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    cases = json.loads(manifest_path.read_text(encoding="utf-8"))["cases"]
    if args.filter:
        cases = [c for c in cases if re.search(args.filter, c["id"])]

    def work(case):
        text = run_engine(args.engine, manifest_path.parent / case["image"], Path(args.binary))
        return case, text, score_case(case["expectedText"], text)

    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(work, cases))

    groups = defaultdict(list)
    rows = []
    for case, text, s in results:
        groups[(case["category"], case.get("degradation", "clean"))].append(s)
        groups[("ALL", "")].append(s)
        rows.append({"id": case["id"], **s, "text": text})
        if args.show:
            print(f"--- {case['id']}  char={s['char_acc']:.3f} word={s['word_acc']:.3f} num={s['num_acc']:.3f}\n{text.strip()}\n")

    print(f"engine={args.engine}  cases={len(results)}  manifest={manifest_path.relative_to(ROOT) if manifest_path.is_relative_to(ROOT) else manifest_path}")
    print(f"{'category':10} {'degrade':8} {'n':>3} {'char_acc':>9} {'word_acc':>9} {'num_acc':>8}")
    for key in sorted(groups, key=lambda k: (k[0] == "ALL", k)):
        g = groups[key]
        avg = {m: sum(x[m] for x in g) / len(g) for m in ("char_acc", "word_acc", "num_acc")}
        print(f"{key[0]:10} {key[1]:8} {len(g):>3} {avg['char_acc']:>9.3f} {avg['word_acc']:>9.3f} {avg['num_acc']:>8.3f}")
    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    overall = groups[("ALL", "")]
    char_acc = sum(x["char_acc"] for x in overall) / len(overall)
    num_acc = sum(x["num_acc"] for x in overall) / len(overall)
    failed = (args.min_char is not None and char_acc < args.min_char) or (args.min_num is not None and num_acc < args.min_num)
    if failed:
        print(f"REGRESSION: char_acc={char_acc:.3f} (min {args.min_char}) num_acc={num_acc:.3f} (min {args.min_num})")
        sys.exit(1)


if __name__ == "__main__":
    main()
