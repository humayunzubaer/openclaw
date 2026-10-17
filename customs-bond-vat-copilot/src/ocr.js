// OCR স্তর — Tesseract.js (বাংলা + ইংরেজি), সম্পূর্ণ লোকাল।
//
// tesseract.js একটি optional dependency। ইনস্টল না থাকলে অ্যাপ চলবে,
// শুধু OCR বাটন জানাবে কীভাবে চালু করতে হয়।
//
// চালু করতে:  cd customs-bond-vat-copilot && npm install tesseract.js
// প্রথমবার ভাষা-ডেটা (ben, eng) ডাউনলোড হয়; একবার হলে অফলাইনে কাজ করে।

let workerPromise = null;

async function loadTesseract() {
  try {
    return await import("tesseract.js");
  } catch {
    return null;
  }
}

export async function isOcrAvailable() {
  return (await loadTesseract()) !== null;
}

async function getWorker() {
  if (workerPromise) return workerPromise;
  workerPromise = (async () => {
    const mod = await loadTesseract();
    if (!mod) throw new Error("OCR_NOT_INSTALLED");
    // বাংলা + ইংরেজি একসাথে
    const worker = await mod.createWorker(["ben", "eng"]);
    return worker;
  })();
  return workerPromise;
}

/**
 * একটি ইমেজ/PDF বাফার থেকে টেক্সট বের করে।
 * @param {Buffer} buf
 * @returns {Promise<{ text: string }>}
 */
export async function recognize(buf) {
  const worker = await getWorker();
  const { data } = await worker.recognize(buf);
  return { text: data.text ?? "" };
}
