// PDFium wrapper — extract / combine / compress / from_images / text-layer।
// এই stub-এ signature ও PDFium call sequence comment হিসেবে দেওয়া; PDFium link
// করলে TODO অংশ পূরণ করুন। libscanner_core link যাতে ভাঙে না, তাই সব symbol defined।
#include "scanner_core.h"
#include <string>
extern ScStatus sc_ok(); extern ScStatus sc_fail(int, const std::string&);

// #include "fpdfview.h" / "fpdf_edit.h" / "fpdf_ppo.h" / "fpdf_save.h" / "fpdf_text.h"

extern "C" void sc_pdf_init(void) {
  // FPDF_LIBRARY_CONFIG cfg{}; cfg.version = 2; FPDF_InitLibraryWithConfig(&cfg);
}

extern "C" int32_t sc_pdf_page_count(const char* path) {
  (void)path; return -1; // TODO: FPDF_LoadDocument → FPDF_GetPageCount
}

extern "C" ScStatus sc_pdf_from_images(const char* const*, int32_t, double, double, const char*) {
  // TODO: FPDF_CreateNewDocument + FPDFPage_New + FPDFPageObj_NewImageObj +
  //       FPDFImageObj_LoadJpegFileInline + FPDFPage_GenerateContent + FPDF_SaveAsCopy
  return sc_fail(SC_ERR_RUNTIME, "sc_pdf_from_images: link PDFium + implement");
}
extern "C" ScStatus sc_pdf_extract(const char*, const int32_t*, int32_t, const char*) {
  // TODO: FPDF_CreateNewDocument + FPDF_ImportPagesByIndex + FPDF_SaveAsCopy
  return sc_fail(SC_ERR_RUNTIME, "sc_pdf_extract: link PDFium + implement");
}
extern "C" ScStatus sc_pdf_combine(const char* const*, int32_t, const char*) {
  // TODO: প্রতি src → FPDF_ImportPages(dst, src, NULL, FPDF_GetPageCount(dst))
  return sc_fail(SC_ERR_RUNTIME, "sc_pdf_combine: link PDFium + implement");
}
extern "C" ScStatus sc_pdf_compress(const char*, int32_t, int32_t, const char*) {
  // TODO: image object recompress (GetBitmap→resize→LoadJpegInline) + SaveAsCopy
  return sc_fail(SC_ERR_RUNTIME, "sc_pdf_compress: link PDFium + implement");
}
extern "C" ScStatus sc_pdf_add_text_layer(const char*, const char*, const char*, const char*) {
  // TODO: FPDFText_LoadFont(cid=1) + CreateTextObj + SetTextRenderMode(INVISIBLE)
  return sc_fail(SC_ERR_RUNTIME, "sc_pdf_add_text_layer: link PDFium + implement");
}
