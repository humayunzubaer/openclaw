"""HTTP API around the Personal Scanner OCR engine.

Runs `ps_ocr --bundle` once per page and returns text, table cells and, for
BEPZA import permits, the extracted fields with their self-check issues.

    POST /v1/scan     multipart field "file" (JPEG/PNG/TIFF/WebP/PDF)
                      or JSON {"file_url": "https://..."};
                      optional ?page=N reads only page N of a PDF
    GET  /health

Settings (environment):
    PS_API_KEY        required header X-API-Key value; unset = no auth (local use only)
    PS_OCR_BIN        engine binary (default: ps_ocr on PATH)
    PS_MAX_UPLOAD_MB  upload size limit (default 25)
    PS_MAX_PAGES      PDF page limit (default 30)
    PS_PDF_DPI        PDF render resolution (default 300)
    PS_CONCURRENCY    pages recognized in parallel (default 2)
    PS_PAGE_TIMEOUT   seconds per page (default 180)
"""

from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import os
import shutil
import socket
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request

API_KEY = os.environ.get("PS_API_KEY", "")
OCR_BIN = os.environ.get("PS_OCR_BIN") or shutil.which("ps_ocr") or "ps_ocr"
MAX_BYTES = int(os.environ.get("PS_MAX_UPLOAD_MB", "25")) * 1024 * 1024
MAX_PAGES = int(os.environ.get("PS_MAX_PAGES", "30"))
PDF_DPI = int(os.environ.get("PS_PDF_DPI", "300"))
PAGE_TIMEOUT = int(os.environ.get("PS_PAGE_TIMEOUT", "180"))
SLOTS = asyncio.Semaphore(int(os.environ.get("PS_CONCURRENCY", "2")))

IMAGE_MAGIC = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"II*\x00": ".tif",
    b"MM\x00*": ".tif",
}

app = FastAPI(title="Personal Scanner OCR", version="1.0")


def require_key(x_api_key: str = Header(default="")) -> None:
    if API_KEY and not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(401, "invalid or missing X-API-Key")


def detect_kind(data: bytes) -> str:
    if data.startswith(b"%PDF"):
        return ".pdf"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    for magic, ext in IMAGE_MAGIC.items():
        if data.startswith(magic):
            return ext
    raise HTTPException(415, "unsupported file type: send JPEG, PNG, TIFF, WebP or PDF")


def fetch_url(url: str) -> bytes:
    # The server fetches the URL itself, so only public https hosts are
    # allowed (no localhost, private or link-local addresses).
    parts = urllib.parse.urlparse(url)
    if parts.scheme != "https" or not parts.hostname:
        raise HTTPException(400, "file_url must be an https URL")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443)
    except socket.gaierror as exc:
        raise HTTPException(400, f"cannot resolve {parts.hostname}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise HTTPException(400, "file_url host is not a public address")
    req = urllib.request.Request(url, headers={"User-Agent": "personal-scanner/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read(MAX_BYTES + 1)
    except OSError as exc:
        raise HTTPException(502, f"could not download file_url: {exc}") from exc
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file is too large")
    return data


async def read_input(request: Request) -> tuple[bytes, str]:
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or isinstance(upload, str):
            raise HTTPException(400, 'multipart body needs a "file" field')
        data = await upload.read(MAX_BYTES + 1)
        name = upload.filename or "upload"
    elif ctype.startswith("application/json"):
        body = await request.json()
        url = body.get("file_url") if isinstance(body, dict) else None
        if not isinstance(url, str):
            raise HTTPException(400, 'JSON body needs "file_url"')
        data = await asyncio.to_thread(fetch_url, url)
        name = Path(urllib.parse.urlparse(url).path).name or "download"
    else:
        raise HTTPException(415, "send multipart/form-data or application/json")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file is too large")
    if not data:
        raise HTTPException(400, "empty file")
    return data, name


async def run(cmd: list[str], timeout: int) -> bytes:
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise HTTPException(504, f"{Path(cmd[0]).name} timed out")
    if proc.returncode != 0:
        raise HTTPException(422, f"{Path(cmd[0]).name} failed: {err.decode(errors='replace').strip()[:300]}")
    return out


async def pdf_pages(pdf: Path, workdir: Path, only: int | None) -> tuple[int, list[tuple[int, Path]]]:
    info = (await run(["pdfinfo", str(pdf)], 60)).decode(errors="replace")
    count = next((int(l.split()[-1]) for l in info.splitlines() if l.startswith("Pages:")), 0)
    if count == 0:
        raise HTTPException(422, "PDF has no pages")
    if only is not None and not 1 <= only <= count:
        raise HTTPException(400, f"page must be between 1 and {count}")
    if only is None and count > MAX_PAGES:
        raise HTTPException(413, f"PDF has {count} pages; the limit is {MAX_PAGES} (or request one page at a time)")
    first, last = (only, only) if only else (1, count)
    span = ["-f", str(first), "-l", str(last)]

    # Scanner apps (Adobe Scan, CamScanner) store each page as one photo.
    # Extracting that photo keeps its native pixels; rendering the page
    # would resample it. Pages that are not a single JPEG/PNG are rendered.
    listing = (await run(["pdfimages", "-list", *span, str(pdf)], 60)).decode(errors="replace")
    per_page: dict[int, int] = {}
    for line in listing.splitlines()[2:]:
        cols = line.split()
        if len(cols) > 2 and cols[2] == "image":
            per_page[int(cols[0])] = per_page.get(int(cols[0]), 0) + 1
    await run(["pdfimages", "-all", "-p", *span, str(pdf), str(workdir / "img")], 60 * (last - first + 1))

    pages: list[tuple[int, Path]] = []
    for n in range(first, last + 1):
        found = [p for p in workdir.glob(f"img-{n:03d}-*") if p.suffix in (".jpg", ".png")]
        if per_page.get(n) == 1 and len(found) == 1:
            pages.append((n, found[0]))
            continue
        prefix = workdir / f"page-{n:03d}"
        await run(["pdftoppm", "-r", str(PDF_DPI), "-png", "-singlefile", "-f", str(n), "-l", str(n), str(pdf), str(prefix)], 120)
        pages.append((n, prefix.with_suffix(".png")))
    return count, pages


def page_text(page: dict) -> str:
    # Same layout as Page::text(): one line per text line or table row,
    # table cells separated by tabs.
    out: list[str] = []
    for block in page.get("blocks", []):
        if block["kind"] == "text":
            out.extend(line["text"] for line in block["lines"])
            continue
        for r in range(block["rows"]):
            cells = [c["text"] for c in block["cells"] if c["row"] == r and c["text"]]
            if cells:
                out.append("\t".join(cells))
    return "\n".join(out)


async def recognize(image: Path, number: int) -> dict:
    async with SLOTS:
        raw = await run([OCR_BIN, "--bundle", str(image)], PAGE_TIMEOUT)
    bundle = json.loads(raw)
    page = bundle["page"]
    result = {
        "page": number,
        "script": page["script"],
        "page_found": page["pageFound"],
        "skew_degrees": page["skew"],
        "text": page_text(page),
        "blocks": page["blocks"],
    }
    if bundle["permit"]["detected"]:
        result["import_permit"] = bundle["permit"]
    return result


@app.get("/health")
async def health() -> dict:
    return {"ok": Path(OCR_BIN).exists() or shutil.which(OCR_BIN) is not None, "engine": "personal-scanner"}


@app.post("/v1/scan", dependencies=[Depends(require_key)])
async def scan(request: Request, page: int | None = None) -> dict:
    started = time.monotonic()
    data, name = await read_input(request)
    kind = detect_kind(data)
    with tempfile.TemporaryDirectory(prefix="ps-") as tmp:
        workdir = Path(tmp)
        source = workdir / f"input{kind}"
        source.write_bytes(data)
        if kind == ".pdf":
            count, images = await pdf_pages(source, workdir, page)
        elif page not in (None, 1):
            raise HTTPException(400, "an image has only page 1")
        else:
            count, images = 1, [(1, source)]
        pages = await asyncio.gather(*(recognize(img, n) for n, img in images))
    permits = [p["page"] for p in pages if "import_permit" in p]
    return {
        "file_name": name,
        "page_count": count,
        "pages_returned": [p["page"] for p in pages],
        "document_type": "import_permit" if permits else "general",
        "pages": pages,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }
