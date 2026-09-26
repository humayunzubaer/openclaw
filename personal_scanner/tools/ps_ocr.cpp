// Desktop front end for the Personal Scanner core, used by the benchmark.
//
//   ps_ocr [--json] [--lang ben+eng] [--tessdata DIR] [--debug DIR]
//          [--no-page] [--no-tables] [--no-rereads] IMAGE
#include <cstdio>
#include <cstring>
#include <iostream>
#include <string>

#include <opencv2/imgcodecs.hpp>

#include "ps/engine.hpp"

int main(int argc, char** argv) {
  ps::Options opt;
  bool json = false;
  std::string image;
  for (int i = 1; i < argc; ++i) {
    const std::string a = argv[i];
    auto next = [&]() -> std::string {
      if (i + 1 >= argc) { std::cerr << a << " needs a value\n"; std::exit(2); }
      return argv[++i];
    };
    if (a == "--json") json = true;
    else if (a == "--lang") opt.languages = next();
    else if (a == "--tessdata") opt.tessdataDir = next();
    else if (a == "--debug") opt.debugDir = next();
    else if (a == "--no-page") opt.detectPage = false;
    else if (a == "--no-tables") opt.detectTables = false;
    else if (a == "--no-rereads") opt.numericRereads = false;
    else if (!a.empty() && a[0] == '-') { std::cerr << "unknown option " << a << '\n'; return 2; }
    else image = a;
  }
  if (const char* env = std::getenv("PS_TESSDATA"); env && opt.tessdataDir.empty()) opt.tessdataDir = env;
  if (const char* env = std::getenv("PS_LANG")) opt.languages = env;
  if (image.empty()) {
    std::cerr << "usage: ps_ocr [--json] [--lang L] [--tessdata DIR] [--debug DIR] IMAGE\n";
    return 2;
  }
  const cv::Mat img = cv::imread(image, cv::IMREAD_COLOR);
  if (img.empty()) {
    std::cerr << "cannot read " << image << '\n';
    return 1;
  }
  try {
    ps::Engine engine(opt);
    const ps::Page page = engine.recognize(img);
    std::cout << (json ? page.json() + "\n" : page.text());
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
  return 0;
}
