cmake_minimum_required(VERSION 3.18)
project(personal_scanner_core CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# OpenCV: the Android/iOS SDKs ship OpenCVConfig.cmake; Debian/Ubuntu's split
# -dev packages may not, so fall back to the plain libraries.
find_package(OpenCV QUIET COMPONENTS core imgproc imgcodecs)
if(NOT OpenCV_FOUND)
  find_path(OpenCV_INCLUDE_DIRS opencv2/core.hpp PATH_SUFFIXES opencv4 REQUIRED)
  foreach(m core imgproc imgcodecs)
    find_library(OpenCV_${m}_LIB opencv_${m} REQUIRED)
    list(APPEND OpenCV_LIBS ${OpenCV_${m}_LIB})
  endforeach()
endif()

find_package(Tesseract CONFIG QUIET)
if(TARGET Tesseract::libtesseract)
  set(TESSERACT_LIBS Tesseract::libtesseract)
else()
  find_path(TESSERACT_INCLUDE tesseract/baseapi.h REQUIRED)
  find_library(TESSERACT_LIB tesseract REQUIRED)
  find_library(LEPTONICA_LIB NAMES leptonica lept REQUIRED)
  set(TESSERACT_LIBS ${TESSERACT_LIB} ${LEPTONICA_LIB})
endif()

add_library(ps_core STATIC
  core/src/engine.cpp
  core/src/import_permit.cpp
  core/src/imaging.cpp
  core/src/tables.cpp
  core/src/text.cpp)
target_include_directories(ps_core PUBLIC core/include ${OpenCV_INCLUDE_DIRS} PRIVATE ${TESSERACT_INCLUDE})
target_link_libraries(ps_core PUBLIC ${OpenCV_LIBS} ${TESSERACT_LIBS})
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(ps_core PRIVATE -Wall -Wextra -Wno-unused-parameter)
endif()

option(PS_BUILD_TOOLS "Build desktop tools (ps_ocr)" ON)
if(PS_BUILD_TOOLS)
  add_executable(ps_ocr tools/ps_ocr.cpp)
  target_link_libraries(ps_ocr PRIVATE ps_core)
endif()

enable_testing()
add_executable(import_permit_test tests/import_permit_test.cpp)
target_link_libraries(import_permit_test PRIVATE ps_core)
add_test(NAME import_permit COMMAND import_permit_test)
