// মডিউল রেজিস্ট্রি — সব অডিট টাইপ এখানে নিবন্ধিত হয়।
// নতুন টাইপ (প্রচ্ছন্ন, পোশাক শিল্প, VAT limited/proprietorship) যোগ করা মানে
// শুধু নতুন মডিউল ফাইল বানিয়ে এখানে register করা।

import { bondDirectNonGarments } from "./bond-direct-non-garments.js";

/** সব উপলব্ধ মডিউল (Phase 1-এ একটি; পরে বাড়বে) */
export const modules = [bondDirectNonGarments];

// ভবিষ্যতের মডিউল — কাঠামো প্রস্তুত, বিষয়বস্তু পরে যোগ হবে:
export const plannedModules = [
  { id: "bond-deemed-export", category: "bond", title: "বন্ড অডিট — প্রচ্ছন্ন রপ্তানি", status: "planned" },
  { id: "bond-direct-garments", category: "bond", title: "বন্ড অডিট — সরাসরি (পোশাক শিল্প)", status: "planned" },
  { id: "vat-limited", category: "vat", title: "ভ্যাট অডিট — লিমিটেড কোম্পানি", status: "planned" },
  { id: "vat-proprietorship", category: "vat", title: "ভ্যাট অডিট — প্রোপ্রাইটরশিপ", status: "planned" },
];

export function getModule(id) {
  return modules.find((m) => m.id === id) ?? null;
}

export function listModules() {
  const active = modules.map((m) => ({ id: m.id, category: m.category, title: m.title, status: "active" }));
  return [...active, ...plannedModules];
}
