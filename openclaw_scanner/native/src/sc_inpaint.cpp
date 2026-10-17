#include "scanner_core.h"
#include "dart_api_dl.h"
#include <onnxruntime_cxx_api.h>
#include <opencv2/opencv.hpp>
#include <thread>
#include <vector>
#include <array>
#include <cstring>
#if defined(__ANDROID__)
  #include <nnapi_provider_factory.h>
#elif defined(__APPLE__)
  #include <coreml_provider_factory.h>
#endif

extern cv::Mat asMat(const ScImage*); extern ScImage viewOf(cv::Mat&);
extern ScStatus sc_ok(); extern ScStatus sc_fail(int, const std::string&);
struct ScScratch { std::vector<cv::Mat> pool; cv::Mat* find(const uint8_t*); };

extern "C" intptr_t sc_init_dart_api(void* data) { return Dart_InitializeApiDL(data); }

static void postList2(Dart_Port port, int64_t a, int64_t b) {
  Dart_CObject i0; i0.type = Dart_CObject_kInt64; i0.value.as_int64 = a;
  Dart_CObject i1; i1.type = Dart_CObject_kInt64; i1.value.as_int64 = b;
  Dart_CObject* items[2] = {&i0, &i1};
  Dart_CObject msg; msg.type = Dart_CObject_kArray;
  msg.value.as_array.length = 2; msg.value.as_array.values = items;
  Dart_PostCObject_DL(port, &msg);
}

struct ScInpainter {
  Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "lama"};
  Ort::Session session{nullptr};
  std::string inImg, inMask, outName;
};

extern "C" ScStatus sc_inpaint_create(const char* model_path, int32_t accel, ScInpainter** out) {
  try {
    Ort::SessionOptions so; so.SetIntraOpNumThreads(2);
    so.SetGraphOptimizationLevel(ORT_ENABLE_ALL);
#if defined(__ANDROID__)
    if (accel == SC_NNAPI) Ort::ThrowOnError(OrtSessionOptionsAppendExecutionProvider_Nnapi(so, 0));
#elif defined(__APPLE__)
    if (accel == SC_COREML) Ort::ThrowOnError(OrtSessionOptionsAppendExecutionProvider_CoreML(so, 0));
#endif
    auto* inp = new ScInpainter();
    inp->session = Ort::Session(inp->env, model_path, so);
    Ort::AllocatorWithDefaultOptions a;
    inp->inImg  = inp->session.GetInputNameAllocated(0, a).get();
    inp->inMask = inp->session.GetInputNameAllocated(1, a).get();
    inp->outName = inp->session.GetOutputNameAllocated(0, a).get();
    *out = inp; return sc_ok();
  } catch (const std::exception& e) { return sc_fail(SC_ERR_MODEL, e.what()); }
}
extern "C" void sc_inpaint_destroy(ScInpainter* i) { delete i; }

static void runTile(ScInpainter* inp, cv::Mat& tileBGR, const cv::Mat& tileMask) {
  cv::Mat rgb; cv::cvtColor(tileBGR, rgb, cv::COLOR_BGR2RGB);
  rgb.convertTo(rgb, CV_32FC3, 1.0 / 255);
  cv::Mat mask; tileMask.convertTo(mask, CV_32FC1, 1.0 / 255);
  const int H = rgb.rows, W = rgb.cols;
  std::vector<float> img(3 * H * W), msk(H * W);
  std::vector<cv::Mat> ch(3); cv::split(rgb, ch);
  for (int c = 0; c < 3; ++c) std::memcpy(&img[c * H * W], ch[c].data, sizeof(float) * H * W);
  std::memcpy(msk.data(), mask.data, sizeof(float) * H * W);

  Ort::MemoryInfo mi = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
  std::array<int64_t, 4> is{1, 3, H, W}, ms{1, 1, H, W};
  Ort::Value ti = Ort::Value::CreateTensor<float>(mi, img.data(), img.size(), is.data(), 4);
  Ort::Value tm = Ort::Value::CreateTensor<float>(mi, msk.data(), msk.size(), ms.data(), 4);
  const char* ins[] = {inp->inImg.c_str(), inp->inMask.c_str()};
  const char* outs[] = {inp->outName.c_str()};
  Ort::Value inv[] = {std::move(ti), std::move(tm)};
  auto res = inp->session.Run(Ort::RunOptions{nullptr}, ins, inv, 2, outs, 1);

  float* o = res[0].GetTensorMutableData<float>();
  std::vector<cv::Mat> oc(3);
  for (int c = 0; c < 3; ++c) oc[c] = cv::Mat(H, W, CV_32FC1, o + c * H * W);
  cv::Mat outRgb; cv::merge(oc, outRgb);
  outRgb.convertTo(outRgb, CV_8UC3, 255.0);
  cv::cvtColor(outRgb, outRgb, cv::COLOR_RGB2BGR);
  outRgb.copyTo(tileBGR, tileMask > 127);
}

extern "C" ScStatus sc_inpaint_run_scratch_async(
    ScInpainter* inp, ScScratch* s, const ScImage* src, const ScImage* mask,
    int32_t tile, int32_t overlap, int64_t port, ScImage* out_view) {
  cv::Mat srcM = asMat(src).clone();
  cv::Mat maskM = asMat(mask).clone();
  s->pool.push_back(srcM);
  cv::Mat* work = &s->pool.back();
  *out_view = viewOf(*work);

  std::thread([inp, work, maskM, tile, overlap, port]() {
    try {
      const int step = tile - overlap;
      int tilesX = (work->cols + step - 1) / step, tilesY = (work->rows + step - 1) / step;
      int total = std::max(1, tilesX * tilesY), done = 0;
      for (int ty = 0; ty < work->rows; ty += step)
        for (int tx = 0; tx < work->cols; tx += step) {
          cv::Rect r(tx, ty, std::min(tile, work->cols - tx), std::min(tile, work->rows - ty));
          cv::Mat mtile = maskM(r);
          if (cv::countNonZero(mtile.channels() == 1 ? mtile : mtile) > 0) {
            cv::Mat itile = (*work)(r);
            cv::Mat mg; if (mtile.channels() > 1) cv::cvtColor(mtile, mg, cv::COLOR_BGR2GRAY); else mg = mtile;
            runTile(inp, itile, mg);
          }
          postList2(port, 1, (int64_t)(1000.0 * (++done) / total));
        }
      postList2(port, 2, (int64_t)(intptr_t)work->data);
    } catch (const std::exception&) { postList2(port, 3, SC_ERR_RUNTIME); }
  }).detach();

  return sc_ok();
}
