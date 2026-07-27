// রিপোর্ট জেনারেটর — finding + working paper থেকে
// Working Paper, Note Sheet ও Final Audit Report তৈরি করে (Markdown/HTML)।
//
// রিপোর্ট বাংলায়, technical term ইংরেজিতে।

import { resolveLegalRef } from "../knowledge/bond-legal.js";

const bdt = (n) => Number(n || 0).toLocaleString("en-BD");

function evidenceNames(finding, documents) {
  const ids = finding.evidenceDocIds ?? [];
  return ids
    .map((id) => documents.find((d) => d.id === id)?.filename)
    .filter(Boolean)
    .join(", ");
}

/** Working Paper — বিস্তারিত কার্যপত্র */
export function buildWorkingPaper({ audit, module, findings, documents, workingPaper }) {
  const lines = [];
  lines.push(`# Working Paper — ${module.title}`);
  lines.push("");
  lines.push(`**প্রতিষ্ঠান:** ${audit.institution || "—"}  `);
  lines.push(`**নিরীক্ষাকাল (Period):** ${audit.period || "—"}  `);
  lines.push(`**নিরীক্ষক (Auditor):** ${audit.auditor || "—"}  `);
  lines.push(`**তারিখ:** ${new Date().toLocaleDateString("en-CA")}`);
  lines.push("");

  for (const section of module.workingPaperSections) {
    lines.push(`## ${section}`);
    const note = workingPaper?.sections?.[section];
    lines.push(note?.trim() ? note : "_(নোট যুক্ত করুন)_");
    lines.push("");
  }

  lines.push("## Findings সারসংক্ষেপ");
  lines.push("");
  lines.push("| # | Area | পর্যবেক্ষণ | আইন | রাজস্ব প্রভাব (BDT) | Evidence |");
  lines.push("|---|------|-----------|-----|--------------------|----------|");
  findings.forEach((f, i) => {
    const ref = f.legalRef ? resolveLegalRef(f.legalRef)?.citation ?? f.legalRef : "—";
    lines.push(
      `| ${i + 1} | ${f.area || "—"} | ${(f.observation || f.title || "").replace(/\n/g, " ")} | ${ref} | ${bdt(f.revenueImplication)} | ${evidenceNames(f, documents) || "—"} |`,
    );
  });
  return lines.join("\n");
}

/** Note Sheet — সিদ্ধান্তমূলক সংক্ষিপ্ত নোট */
export function buildNoteSheet({ audit, module, findings }) {
  const total = findings.reduce((s, f) => s + Number(f.revenueImplication || 0), 0);
  const high = findings.filter((f) => f.severity === "high").length;
  const lines = [];
  lines.push(`# Note Sheet — ${audit.institution || module.title}`);
  lines.push("");
  lines.push(`নিরীক্ষায় মোট **${findings.length}টি** পর্যবেক্ষণ চিহ্নিত হয়েছে, যার মধ্যে **${high}টি** গুরুতর (high severity)।`);
  lines.push("");
  lines.push(`সম্ভাব্য মোট রাজস্ব প্রভাব: **BDT ${bdt(total)}**।`);
  lines.push("");
  lines.push("## প্রধান পর্যবেক্ষণসমূহ");
  findings
    .filter((f) => f.severity === "high")
    .forEach((f, i) => lines.push(`${i + 1}. ${f.title || f.area}: ${f.observation}`));
  lines.push("");
  lines.push("## সিদ্ধান্ত / সুপারিশ");
  lines.push("_(অনুমোদনকারী কর্তৃপক্ষের সিদ্ধান্ত এখানে লিপিবদ্ধ হবে)_");
  return lines.join("\n");
}

/** Final Audit Report */
export function buildFinalReport({ audit, module, findings, documents }) {
  const total = findings.reduce((s, f) => s + Number(f.revenueImplication || 0), 0);
  const lines = [];
  lines.push(`# চূড়ান্ত নিরীক্ষা প্রতিবেদন (Final Audit Report)`);
  lines.push(`## ${module.title}`);
  lines.push("");
  lines.push(`**প্রতিষ্ঠান:** ${audit.institution || "—"}  `);
  lines.push(`**নিরীক্ষাকাল:** ${audit.period || "—"}  `);
  lines.push(`**নিরীক্ষক:** ${audit.auditor || "—"}  `);
  lines.push(`**প্রতিবেদন তারিখ:** ${new Date().toLocaleDateString("en-CA")}`);
  lines.push("");
  lines.push("## ১. ভূমিকা");
  lines.push(`${audit.institution || "প্রতিষ্ঠানটি"} একটি সরাসরি রপ্তানিকারক (পোশাক শিল্প ব্যতীত) বন্ড সুবিধাভোগী প্রতিষ্ঠান। উক্ত প্রতিষ্ঠানের বন্ড কার্যক্রম নিরীক্ষা করা হয়।`);
  lines.push("");
  lines.push("## ২. নিরীক্ষার আওতা ও পদ্ধতি");
  lines.push(`সংগৃহীত নথি: ${documents.length}টি। যাচাইকৃত ক্ষেত্র: ${module.workingPaperSections.join("; ")}।`);
  lines.push("");
  lines.push("## ৩. পর্যবেক্ষণ ও আইনি ভিত্তি");
  findings.forEach((f, i) => {
    const ref = f.legalRef ? resolveLegalRef(f.legalRef) : null;
    lines.push(`### ৩.${i + 1} ${f.title || f.area}`);
    lines.push(`**পর্যবেক্ষণ:** ${f.observation || "—"}`);
    if (ref) lines.push(`**আইনি ভিত্তি:** ${ref.title} — ${ref.citation}`);
    if (Number(f.revenueImplication)) lines.push(`**রাজস্ব প্রভাব:** BDT ${bdt(f.revenueImplication)}`);
    const ev = evidenceNames(f, documents);
    if (ev) lines.push(`**Evidence:** ${ev}`);
    lines.push("");
  });
  lines.push("## ৪. রাজস্ব প্রভাব (সারসংক্ষেপ)");
  lines.push(`চিহ্নিত অসঙ্গতির ভিত্তিতে সম্ভাব্য মোট আদায়যোগ্য/পরিহারযোগ্য রাজস্ব: **BDT ${bdt(total)}**।`);
  lines.push("");
  lines.push("## ৫. সুপারিশ");
  lines.push("_(সুপারিশ এখানে যুক্ত করুন)_");
  return lines.join("\n");
}

export function buildReport(kind, ctx) {
  if (kind === "working-paper") return buildWorkingPaper(ctx);
  if (kind === "note-sheet") return buildNoteSheet(ctx);
  if (kind === "final") return buildFinalReport(ctx);
  throw new Error(`Unknown report kind: ${kind}`);
}
