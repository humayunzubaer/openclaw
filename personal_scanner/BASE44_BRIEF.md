# Personal Scanner: build brief for the Base44 agent

You are building the user-facing app for **Personal Scanner**, an OCR scanner for Bengali and
English documents. The user is an auditor in Bangladesh who checks Customs & VAT documents:
import permits, UP/UD, Mushak forms, bond registers. **Accuracy of numbers matters more than
anything else.** A wrong digit in an invoice value or a weight is an audit error.

The OCR engine is already built and tested. It runs as an HTTP service on the user's own VPS.
Your job is the app around it: upload, the review screens, storage, history and export.
**Do not build or replace the OCR yourself.**

## 1. Hard rules

1. **All text and numbers come from the OCR API.** Never use an LLM (InvokeLLM or similar) to
   read documents, fill in fields, "fix" numbers or guess missing values. An LLM may only be
   used for optional prose that is clearly labelled as such, and it must never change a field.
2. **Keep the OCR value and the user's correction separately.** When the user edits a field,
   store the original OCR value, the new value, who changed it and when. Never overwrite the
   OCR result in place.
3. **Show every issue the engine reports.** `issues` are the engine's self-checks. An issue with
   `corrected: true` means the engine changed a value because the form's own arithmetic proved
   it; the message holds the value that was read (for example `read 46,310.00, FOB items total
   48,310.00`). Show it with an amber marker. An issue with `corrected: false` means the value
   could not be confirmed. Show it with a red "needs review" marker. A permit cannot be marked
   verified while a red issue is open and unacknowledged.
4. **Documents are confidential.** Use private file storage and signed URLs. Every record
   belongs to the user who created it. Do not make any document public.
5. **The API key is a secret.** Call the OCR API only from a backend function. Never call it
   from browser code.

## 2. Architecture

```
Browser (Base44 app)
  │  upload photo/PDF (private file)            ┌──────────────────────────────┐
  ▼                                             │ User's VPS (Docker)          │
Base44 backend function "scanDocument" ──HTTPS──► Caddy → OCR API :8080        │
  │  POST /v1/scan {file_url}  X-API-Key        │   C++ engine (OpenCV +     │
  │  one call per page for PDFs                 │   Tesseract, Bengali/Eng)  │
  ▼                                             └──────────────────────────────┘
Base44 entities (Document, DocumentPage, ImportPermit, FieldEdit)
```

Secrets to create in Base44: `PS_API_URL` (for example `https://ocr.example.com`) and
`PS_API_KEY`. The user will supply both values.

## 3. OCR API contract

### Requests

`POST {PS_API_URL}/v1/scan` with header `X-API-Key: {PS_API_KEY}`. Send the file in one of
two ways:

- `Content-Type: application/json` with body `{"file_url": "https://..."}`. Use a signed URL
  of the private upload. The server downloads it, and only public `https` URLs are accepted.
- `multipart/form-data` with field `file`.

Accepted file types are JPEG, PNG, TIFF, WebP and PDF. HEIC is not accepted, so convert it to
JPEG first. The upload limit is 25 MB. A full PDF can have at most 30 pages; `?page=N` can read
any page.

Optional query `?page=N` (1-based) reads only page N of a PDF. **Use it**: first call
`?page=1`, read `page_count` from the response, then call pages 2..N one by one. This keeps
every request short (a few seconds) and lets the UI show "page 3 of 7".

`GET {PS_API_URL}/health` returns `{"ok": true}`.

### Response (200)

```json
{
  "file_name": "permit.pdf",
  "page_count": 3,
  "pages_returned": [1],
  "document_type": "import_permit",
  "elapsed_ms": 5200,
  "pages": [
    {
      "page": 1,
      "script": "latin",
      "page_found": true,
      "skew_degrees": -0.6,
      "text": "Import Permit Details - Foreign Import\nPermit date: 05-03-2025\n...",
      "blocks": [
        { "kind": "text", "box": [85, 81, 417, 58],
          "lines": [ { "text": "মাসিক রাজস্ব বিবরণী", "conf": 95.7, "box": [85, 81, 417, 58] } ] },
        { "kind": "table", "box": [100, 340, 1300, 900], "rows": 6, "cols": 4,
          "cells": [ { "row": 0, "col": 1, "text": "খাতের নাম", "conf": 96.0, "box": [294, 344, 583, 138] } ] }
      ],
      "import_permit": {
        "detected": true,
        "fields": {
          "permit_no": "ID0503250042", "permit_date": "05-03-2025",
          "company": "Example Garments BD Ltd.", "invoice_value": "48,310.00",
          "total_net_weight": "5120.40"
        },
        "items": [
          { "hs": "52081200", "quantity": "4200.0", "unit": "KG", "net_weight": "4200.0", "fob": "31,500.00" }
        ],
        "issues": [
          { "field": "invoice_value", "message": "read 46,310.00, FOB items total 48,310.00",
            "suggested": "48,310.00", "corrected": true },
          { "field": "invoice_date", "message": "invoice_date is after the permit date; check the digits",
            "suggested": "", "corrected": false }
        ]
      }
    }
  ]
}
```

(Values above are illustrative.)

- `text`: the page as plain text. One line per text line or table row; table cells are
  separated by a TAB.
- `script`: `"bengali"` or `"latin"`, the model the page was read with.
- `blocks`: reading order, top to bottom. `conf` is 0–100. Show cells or lines below about
  70 with a light highlight so the user knows to look at them. `box` is `[x, y, w, h]` on the
  engine's *straightened* page, not on the original photo, so do not draw boxes over the
  uploaded image.
- `import_permit`: present only when the page is a BEPZA import permit.

### Errors

The body is always `{"detail": "..."}`.

| status | meaning | what the UI does |
|---|---|---|
| 400 | bad request (no file, bad `page`, non-https/private `file_url`) | show the message |
| 401 | wrong API key | "Server key is wrong. Check settings" |
| 413 | file too large / too many pages | ask for a smaller file, or use `?page=` |
| 415 | unsupported type | "Send JPG, PNG, TIFF, WebP or PDF" |
| 422 | the engine could not read the file | mark the page failed and allow retry |
| 502 | could not download `file_url` | retry once, then show an error |
| 504 | page took too long | allow retry |

Typical time is 2–8 s per page. Set the backend fetch timeout to 120 s per page.

## 4. Import permit fields

| key | label (বাংলা / English) |
|---|---|
| permit_no | পারমিট নং / Permit No |
| permit_date | পারমিটের তারিখ / Permit Date |
| company | প্রতিষ্ঠানের নাম / Company |
| source_country | উৎস দেশ / Source Country |
| place_of_load | লোডিং বন্দর / Place of Load |
| place_of_unload | আনলোডিং বন্দর / Place of Unload |
| bl_no | বিল অব লেডিং / B/L No |
| undertaking_no | আন্ডারটেকিং নং / Undertaking No |
| undertaking_date | আন্ডারটেকিং তারিখ / Undertaking Date |
| invoice_no | ইনভয়েস নং / Invoice No |
| invoice_date | ইনভয়েস তারিখ / Invoice Date |
| invoice_value | ইনভয়েস মূল্য / Invoice Value |
| permitted_till | মেয়াদ / Permitted Till |
| total_net_weight | মোট নিট ওজন / Total Net Weight |
| lc_no | এলসি নং / LC No |
| lc_issue | এলসি ইস্যু তারিখ / LC Issue Date |
| bank | ব্যাংক / Bank |
| supplier | সরবরাহকারী / Supplier |

Fields the engine could not find are absent from `fields`. Show them as empty inputs the user
can fill in, and record those entries as manual. Item columns are HS Code, Quantity, Unit,
Net Weight and FOB.

The review screen must recompute and show these checks live, from the user's current values:

- Σ items FOB = Invoice Value
- Σ items Net Weight = Total Net Weight
- Permit No = `ID` + 10 digits, and its first 6 digits are the permit date as ddmmyy

Show ✓ or ✗ next to each check.

## 5. Data model (Base44 entities)

- **Document**: `title`, `file_uri` (private), `file_name`, `mime_type`, `page_count`,
  `document_type` (`general` | `import_permit`), `status` (`uploaded` | `processing` | `done` |
  `partial` | `failed`), `pages_done`, `error`, `notes`.
- **DocumentPage**: `document_id`, `page`, `script`, `text`, `blocks` (JSON), `min_conf`,
  `status`, `error`.
- **ImportPermit**: `document_id`, `page`, `ocr_fields` (JSON, never edited), `ocr_items`
  (JSON), `issues` (JSON), `fields` (JSON, current values), `items` (JSON, current values),
  `review_status` (`needs_review` | `verified`), `verified_by`, `verified_at`.
- **FieldEdit** (audit trail): `permit_id`, `field` (or `items[i].fob`), `ocr_value`,
  `old_value`, `new_value`, `edited_by`, `edited_at`, `reason`.

All entities are readable and writable only by their creator, plus admins.

## 6. Screens

The UI is in Bengali first, with English field names in brackets. It must work on a phone
first: the user often photographs documents.

1. **Home / Documents**: a list with search by title or permit no, a type badge, a status
   badge, and the date.
2. **New scan**: "Take photo" (`<input type="file" accept="image/*" capture="environment">`),
   "Choose file" (images or PDF), and "Add page" to collect several photos into one document.
   Upload privately, create the Document, then call the backend function page by page with a
   progress bar. A failed page can be retried on its own.
3. **Document view**: a tab per page, with the original image or PDF page on one side and
   the result on the other.
   - Text view, with a copy button.
   - Table view: each `table` block drawn as a real grid, with low-confidence cells
     highlighted.
4. **Import permit review**: the fields form (OCR value shown as a hint under each input),
   the items table, the live checks from section 4, and the issues list. Editing creates
   FieldEdit records. The "Mark verified" button stays disabled while red issues are
   unacknowledged.
5. **Export**:
   - TXT: all pages.
   - XLSX: one sheet per table, plus a "Permit" sheet with fields, items and a checks row.
   - JSON: the raw API result.
   - For several import permits: a summary XLSX with one row per permit and the key fields.
     It is the auditor's working sheet.

## 7. Backend function sketch (adapt to the current Base44 SDK)

```ts
import { createClientFromRequest } from "npm:@base44/sdk";

Deno.serve(async (req) => {
  const base44 = createClientFromRequest(req);
  const user = await base44.auth.me();
  if (!user) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const { file_url, page } = await req.json(); // file_url: short-lived signed URL
  const url = new URL("/v1/scan", Deno.env.get("PS_API_URL"));
  if (page) url.searchParams.set("page", String(page));

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": Deno.env.get("PS_API_KEY")! },
    body: JSON.stringify({ file_url }),
    signal: AbortSignal.timeout(120_000),
  });
  const body = await res.json();
  return Response.json(body, { status: res.status });
});
```

The frontend saves the returned pages into DocumentPage and ImportPermit. Store `ocr_fields`
and `ocr_items` from the response unchanged.

## 8. Acceptance checks

- Upload `bench/reference/revenue-table.png`. The table view shows a 6×4 grid with Bengali
  headers, and the text contains "মাসিক রাজস্ব বিবরণী".
- Upload a multi-page PDF. The progress bar counts pages, and each page has its own tab.
- Upload a BEPZA import permit. The review screen opens, the fields are filled, the checks
  show ✓ or ✗, and the issues are listed. A corrected value shows the originally read value.
- Edit a field. A FieldEdit row exists, and the OCR value is still visible.
- Turn off the OCR server. The upload shows a clear error, and the Document is `failed` and
  retryable.
- A second user cannot see the first user's documents.

## 9. Not in scope now (later phases)

- Field profiles for UP, UD, Mushak-6.3 and bond registers. Until then they appear as text
  and tables only.
- Searchable PDF output and a fully offline phone app. The engine is designed to run on the
  phone later.
- Handwriting.

If no OCR server is available, do **not** substitute Tesseract.js or an LLM silently. Show
"OCR server not configured" in settings.
