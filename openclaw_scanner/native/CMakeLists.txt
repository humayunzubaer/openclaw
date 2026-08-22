cmake_minimum_required(VERSION 3.22)
project(scanner_core LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Prebuilt third-party: third_party/<lib>/lib/${ANDROID_ABI}/*.so + include
set(TP ${CMAKE_SOURCE_DIR}/third_party)
set(DART_INCLUDE ${TP}/dart/include)   # Flutter SDK-এর dart-sdk/include থেকে copy

set(SC_SOURCES
  src/sc_common.cpp
  src/sc_opencv.cpp
  src/sc_ocr.cpp
  src/sc_inpaint.cpp
  src/sc_analyze.cpp
  src/sc_pdf.cpp
  ${DART_INCLUDE}/dart_api_dl.c)

# ---------------- Android ----------------
if(ANDROID)
  set(OpenCV_DIR ${TP}/opencv/sdk/native/jni)
  find_package(OpenCV REQUIRED)

  add_library(tesseract SHARED IMPORTED)
  set_target_properties(tesseract PROPERTIES IMPORTED_LOCATION ${TP}/tesseract/lib/${ANDROID_ABI}/libtesseract.so)
  add_library(leptonica SHARED IMPORTED)
  set_target_properties(leptonica PROPERTIES IMPORTED_LOCATION ${TP}/leptonica/lib/${ANDROID_ABI}/libleptonica.so)
  add_library(onnxruntime SHARED IMPORTED)
  set_target_properties(onnxruntime PROPERTIES IMPORTED_LOCATION ${TP}/onnxruntime/lib/${ANDROID_ABI}/libonnxruntime.so)

  add_library(scanner_core SHARED ${SC_SOURCES})
  target_include_directories(scanner_core PRIVATE
    ${CMAKE_SOURCE_DIR}/include ${DART_INCLUDE}
    ${TP}/tesseract/include ${TP}/leptonica/include ${TP}/onnxruntime/include)
  target_link_libraries(scanner_core ${OpenCV_LIBS} tesseract leptonica onnxruntime android log)
  target_link_options(scanner_core PRIVATE $<$<CONFIG:Release>:-Wl,--strip-all>)
endif()

# ---------------- iOS (static lib → xcframework) ----------------
if(APPLE)
  add_library(scanner_core STATIC ${SC_SOURCES})
  set_target_properties(scanner_core PROPERTIES C_VISIBILITY_PRESET default CXX_VISIBILITY_PRESET default)
  target_include_directories(scanner_core PRIVATE
    ${CMAKE_SOURCE_DIR}/include ${DART_INCLUDE}
    ${TP}/ios/opencv2.xcframework/Headers
    ${TP}/ios/onnxruntime.xcframework/Headers
    ${TP}/ios/tesseract/include ${TP}/ios/leptonica/include)
endif()
