// রিপোর্ট export — Word (.doc), Excel (.xlsx), PDF (print-ready HTML)।
// সম্পূর্ণ শূন্য-নির্ভরতা: কোনো npm প্যাকেজ লাগে না, তাই অফলাইনে চলে।
// বাংলা ইউনিকোড ঠিকভাবে রেন্ডার হয় (UTF-8)।

import zlib from "node:zlib";
import { resolveLegalRef } from "../knowledge/bond-legal.js";

const bdt = (n) => Number(n || 0).toLocaleString("en-BD");
const xml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" }[c]));

// ---------------- Word (.doc via HTML) ----------------
// Word HTML-ভিত্তিক .doc নিখুঁতভাবে খোলে; বাংলা ও টেবিল সংরক্ষিত থাকে।

export function toWordDoc({ audit, module, findings, documents, workingPaper }) {
  const rows = findings.map((f, i) => {
    const ref = f.legalRef ? resolveLegalRef(f.legalRef)?.citation ?? f.legalRef : "—";
    return `<tr>
      <td>${i + 1}</td>
      <td>${xml(f.area)}</td>
      <td>${xml(f.observation || f.title)}</td>
      <td>${xml(ref)}</td>
      <td style="text-align:right">${bdt(f.revenueImplication)}</td>
    </tr>`;
  }).join("");

  const total = findings.reduce((s, f) => s + Number(f.revenueImplication || 0), 0);
  const wpSections = module.workingPaperSections
    .map((s) => `<h3>${xml(s)}</h3><p>${xml(workingPaper?.sections?.[s] || "—")}</p>`)
    .join("");

  return `<!doctype html>
<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">
<head><meta charset="utf-8" />
<style>
  body { font-family:"Noto Sans Bengali","Nirmala UI",serif; font-size:12pt; line-height:1.5; }
  h1 { font-size:16pt; } h2 { font-size:14pt; } h3 { font-size:12.5pt; }
  table { border-collapse:collapse; width:100%; } td,th { border:1px solid #333; padding:5px; font-size:10.5pt; vertical-align:top; }
  th { background:#eee; }
</style></head>
<body>
  <h1 style="text-align:center">চূড়ান্ত নিরীক্ষা প্রতিবেদন</h1>
  <h2 style="text-align:center">${xml(module.title)}</h2>
  <p><b>প্রতিষ্ঠান:</b> ${xml(audit.institution || "—")}<br/>
     <b>নিরীক্ষাকাল:</b> ${xml(audit.period || "—")}<br/>
     <b>নিরীক্ষক:</b> ${xml(audit.auditor || "—")}<br/>
     <b>তারিখ:</b> ${new Date().toLocaleDateString("en-CA")}</p>
  <h2>ভূমিকা</h2>
  <p>${xml(audit.institution || "প্রতিষ্ঠানটি")} একটি বন্ড সুবিধাভোগী প্রতিষ্ঠান। উক্ত প্রতিষ্ঠানের বন্ড কার্যক্রম নিরীক্ষা করা হয়। সংগৃহীত নথি: ${documents.length}টি।</p>
  <h2>Working Paper সারাংশ</h2>
  ${wpSections}
  <h2>পর্যবেক্ষণসমূহ (Findings)</h2>
  <table><thead><tr><th>#</th><th>Area</th><th>পর্যবেক্ষণ</th><th>আইন</th><th>রাজস্ব (BDT)</th></tr></thead>
  <tbody>${rows || `<tr><td colspan="5">কোনো finding নেই।</td></tr>`}</tbody></table>
  <p style="margin-top:14px"><b>সম্ভাব্য মোট রাজস্ব প্রভাব: BDT ${bdt(total)}</b></p>
</body></html>`;
}

// ---------------- PDF (print-ready HTML) ----------------
// ব্রাউজারে খুলে স্বয়ংক্রিয়ভাবে print/Save-as-PDF ডায়ালগ আনে — অফলাইন, নিখুঁত বাংলা।

export function toPrintablePdfHtml(ctx) {
  const doc = toWordDoc(ctx);
  return doc.replace("</body>", `<script>window.onload=()=>window.print()</script></body>`);
}

// ---------------- Excel (.xlsx, zero-dependency) ----------------

/** findings + summary → xlsx Buffer */
export function toXlsx({ audit, module, findings }) {
  const total = findings.reduce((s, f) => s + Number(f.revenueImplication || 0), 0);

  const headerRow = ["#", "Area", "পর্যবেক্ষণ", "আইন", "Severity", "রাজস্ব (BDT)"];
  const dataRows = findings.map((f, i) => [
    i + 1,
    f.area || "",
    f.observation || f.title || "",
    (f.legalRef ? resolveLegalRef(f.legalRef)?.citation ?? f.legalRef : ""),
    f.severity || "",
    Number(f.revenueImplication || 0),
  ]);
  const metaRows = [
    ["প্রতিষ্ঠান", audit.institution || ""],
    ["মডিউল", module.title],
    ["নিরীক্ষাকাল", audit.period || ""],
    ["নিরীক্ষক", audit.auditor || ""],
    ["মোট রাজস্ব প্রভাব (BDT)", total],
    [],
  ];
  const rows = [...metaRows, headerRow, ...dataRows];
  return buildXlsx(rows);
}

// --- minimal OOXML spreadsheet writer ---

function colRef(n) {
  let s = "";
  n++;
  while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); }
  return s;
}

function sheetXml(rows) {
  const body = rows.map((cells, r) => {
    const cx = cells.map((v, c) => {
      const ref = `${colRef(c)}${r + 1}`;
      if (typeof v === "number") return `<c r="${ref}"><v>${v}</v></c>`;
      if (v === undefined || v === null || v === "") return `<c r="${ref}"/>`;
      return `<c r="${ref}" t="inlineStr"><is><t xml:space="preserve">${xml(v)}</t></is></c>`;
    }).join("");
    return `<row r="${r + 1}">${cx}</row>`;
  }).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${body}</sheetData></worksheet>`;
}

function buildXlsx(rows) {
  const files = {
    "[Content_Types].xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>`,
    "_rels/.rels": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`,
    "xl/workbook.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Audit" sheetId="1" r:id="rId1"/></sheets></workbook>`,
    "xl/_rels/workbook.xml.rels": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>`,
    "xl/worksheets/sheet1.xml": sheetXml(rows),
  };
  const entries = Object.entries(files).map(([name, content]) => ({ name, data: Buffer.from(content, "utf8") }));
  return zipStore(entries);
}

// --- CRC32 + minimal ZIP (deflate) writer ---

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function zipStore(entries) {
  const chunks = [];
  const central = [];
  let offset = 0;

  for (const { name, data } of entries) {
    const nameBuf = Buffer.from(name, "utf8");
    const comp = zlib.deflateRawSync(data);
    const crc = crc32(data);

    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);       // version needed
    local.writeUInt16LE(0x0800, 6);   // UTF-8 filename flag
    local.writeUInt16LE(8, 8);        // method: deflate
    local.writeUInt16LE(0, 10);       // time
    local.writeUInt16LE(0, 12);       // date
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(comp.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    local.writeUInt16LE(0, 28);
    chunks.push(local, nameBuf, comp);

    const cen = Buffer.alloc(46);
    cen.writeUInt32LE(0x02014b50, 0);
    cen.writeUInt16LE(20, 4);
    cen.writeUInt16LE(20, 6);
    cen.writeUInt16LE(0x0800, 8);
    cen.writeUInt16LE(8, 10);
    cen.writeUInt16LE(0, 12);
    cen.writeUInt16LE(0, 14);
    cen.writeUInt32LE(crc, 16);
    cen.writeUInt32LE(comp.length, 20);
    cen.writeUInt32LE(data.length, 24);
    cen.writeUInt16LE(nameBuf.length, 28);
    cen.writeUInt32LE(offset, 42);
    central.push(Buffer.concat([cen, nameBuf]));

    offset += local.length + nameBuf.length + comp.length;
  }

  const centralBuf = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(centralBuf.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...chunks, centralBuf, end]);
}
