"""Key-field accuracy on real documents.

A field counts as correct when its exact value appears in the OCR output
(whitespace collapsed). This is what matters for audit work: a permit number,
date or amount is either reproduced exactly or it is wrong.

The field manifests live in bench/private/ (gitignored): real documents never
go into the repository.

Usage:
  python3 bench/field_score.py bench/private/ip/fields.json [--engine ps|raw] [--show-misses]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score import ROOT, run_engine  # noqa: E402


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--engine", choices=["raw", "ps"], default="ps")
    ap.add_argument("--binary", default=str(ROOT / "build/ps_ocr"))
    ap.add_argument("--show-misses", action="store_true")
    ap.add_argument("--extract", action="store_true",
                    help="score structured extraction (ps_ocr --permit) instead of plain-text containment")
    args = ap.parse_args()

    path = Path(args.manifest)
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]

    def work(case):
        if args.extract:
            # One OpenMP thread per process: parallel Tesseract runs otherwise
            # spin-wait on each other and stall.
            env = dict(os.environ, OMP_THREAD_LIMIT="1")
            res = subprocess.run([args.binary, "--permit", str(path.parent / case["image"])], capture_output=True,
                                 env=env, timeout=600)
            data = json.loads(res.stdout.decode("utf-8") or "{}")
            got = dict(data.get("fields", {}))
            got["total_nw"] = got.pop("total_net_weight", "")
            for i, item in enumerate(data.get("items", []), 1):
                got[f"hs_{i}"], got[f"nw_{i}"], got[f"fob_{i}"], got[f"qty_{i}"] = (
                    item["hs"], item["net_weight"], item["fob"], item["quantity"])
            return case, got
        return case, collapse(run_engine(args.engine, path.parent / case["image"], Path(args.binary)))

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(work, cases))

    total = hit = 0
    for case, text in results:
        if args.extract:
            misses = [(k, f"{v}  (got {text.get(k, '-')})") for k, v in case["fields"].items()
                      if collapse(text.get(k, "")).rstrip(".") != collapse(v).rstrip(".")]
        else:
            misses = [(k, v) for k, v in case["fields"].items() if collapse(v) not in text]
        n = len(case["fields"])
        total += n
        hit += n - len(misses)
        print(f"{case['id']:8} {n - len(misses):>3}/{n:<3} {(n - len(misses)) / n:6.1%}")
        if args.show_misses:
            for k, v in misses:
                print(f"         miss {k}: {v}")
    print(f"{'ALL':8} {hit:>3}/{total:<3} {hit / total:6.1%}  engine={args.engine}")


if __name__ == "__main__":
    main()
