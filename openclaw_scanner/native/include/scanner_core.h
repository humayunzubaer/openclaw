#ifndef SCANNER_CORE_H
#define SCANNER_CORE_H
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum { SC_OK = 0, SC_ERR_IO = 1, SC_ERR_MODEL = 2,
               SC_ERR_INVALID = 3, SC_ERR_RUNTIME = 4 } ScCode;

typedef struct { int32_t code; const char* message; } ScStatus;

typedef enum { SC_GRAY8 = 0, SC_RGBA8888 = 1, SC_RGB888 = 2 } ScFormat;
typedef enum { SC_CPU = 0, SC_NNAPI = 1, SC_COREML = 2, SC_XNNPACK = 3 } ScAccel;

typedef struct {
  uint8_t* data;
  int32_t  width;
  int32_t  height;
  int32_t  stride;
  int32_t  format;
} ScImage;

typedef struct { float x, y; } ScPoint;
typedef struct { ScPoint tl, tr, br, bl; } ScQuad;

// --- lifecycle / memory ---
void sc_image_free(ScImage* img);
void sc_string_free(char* utf8);
ScStatus sc_image_save_file(const ScImage* img, const char* path, int32_t quality);

// --- scratch arena ---
typedef struct ScScratch ScScratch;
ScStatus sc_scratch_create(int32_t max_bytes, ScScratch** out);
ScStatus sc_scratch_load_file(ScScratch* s, const char* path, ScImage* out_view);
ScStatus sc_scratch_preprocess_for_ocr(ScScratch* s, ScImage* io_view);
ScStatus sc_scratch_save_file(ScScratch* s, const ScImage* view, const char* path, int32_t quality);
void     sc_scratch_reset(ScScratch* s);
void     sc_scratch_destroy(ScScratch* s);

// --- OpenCV image processing ---
ScStatus sc_detect_document_quad(const ScImage* src, ScQuad* out_quad);
ScStatus sc_warp_perspective(const ScImage* src, const ScQuad* quad, ScImage* out);
ScStatus sc_dewarp_book(const ScImage* src, ScImage* out);
ScStatus sc_remove_shadow(const ScImage* src, ScImage* out);
ScStatus sc_preprocess_for_ocr(const ScImage* src, ScImage* out);
ScStatus sc_resize(const ScImage* src, int32_t w, int32_t h, int32_t interp, ScImage* out);

// --- Tesseract OCR (ben LSTM) ---
typedef struct ScOcrEngine ScOcrEngine;
ScStatus sc_ocr_create(const char* tessdata_dir, const char* lang, ScOcrEngine** out_engine);
ScStatus sc_ocr_recognize(ScOcrEngine* engine, const ScImage* page, char** out_json);
void     sc_ocr_destroy(ScOcrEngine* engine);

// --- Dart async bridge ---
intptr_t sc_init_dart_api(void* init_data);

// --- Inpainting (LaMa via ONNX Runtime) ---
typedef struct ScInpainter ScInpainter;
typedef void (*ScProgressCb)(int32_t job_tag, float progress);
ScStatus sc_inpaint_create(const char* onnx_model_path, int32_t accel, ScInpainter** out);
ScStatus sc_inpaint_run_scratch_async(
    ScInpainter* inp, ScScratch* s, const ScImage* src, const ScImage* mask,
    int32_t tile_size, int32_t overlap, int64_t dart_port, ScImage* out_view);
void     sc_inpaint_destroy(ScInpainter* inp);

// --- Hand/finger segmentation + auto analysis ---
typedef struct ScHandSegmenter ScHandSegmenter;
ScStatus sc_handseg_create(const char* onnx_path, int32_t accel, ScHandSegmenter** out);
void     sc_handseg_destroy(ScHandSegmenter* hs);
ScStatus sc_detect_shadow_mask(const ScImage* proxy, ScImage* out_mask);
ScStatus sc_detect_stray_marks(const ScImage* proxy, ScImage* out_mask);
ScStatus sc_mask_to_contours(const ScImage* mask, double epsilon_frac,
                             double min_area_frac, char** out_json);
ScStatus sc_auto_analyze(ScHandSegmenter* hs, ScScratch* s, const char* src_path,
                         int32_t max_dim, char** out_json);

// --- PDF (PDFium) ---
void     sc_pdf_init(void);
int32_t  sc_pdf_page_count(const char* path);
ScStatus sc_pdf_from_images(const char* const* jpg_paths, int32_t count,
                            double page_w_pt, double page_h_pt, const char* out_path);
ScStatus sc_pdf_extract(const char* src_path, const int32_t* indices, int32_t count,
                        const char* out_path);
ScStatus sc_pdf_combine(const char* const* src_paths, int32_t count, const char* out_path);
ScStatus sc_pdf_compress(const char* src_path, int32_t target_dpi, int32_t quality,
                         const char* out_path);
ScStatus sc_pdf_add_text_layer(const char* pdf_in, const char* pdf_out,
                               const char* font_ttf_path, const char* placements_json);

#ifdef __cplusplus
}
#endif
#endif
