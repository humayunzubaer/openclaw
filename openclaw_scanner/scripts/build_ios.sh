#!/usr/bin/env bash
set -euo pipefail
TC="third_party/ios-cmake/ios.toolchain.cmake"   # leetal/ios-cmake

configure_build() {  # $1=PLATFORM  $2=build dir
  cmake -B "$2" -G Xcode -S native \
    -DCMAKE_TOOLCHAIN_FILE="$TC" -DPLATFORM="$1" \
    -DDEPLOYMENT_TARGET=14.0 -DENABLE_BITCODE=OFF -DCMAKE_BUILD_TYPE=Release
  cmake --build "$2" --config Release
}

configure_build OS64            build/ios-device
configure_build SIMULATORARM64  build/ios-sim-arm64
configure_build SIMULATOR64     build/ios-sim-x64

DEV="build/ios-device/Release-iphoneos/libscanner_core.a"
SARM="build/ios-sim-arm64/Release-iphonesimulator/libscanner_core.a"
SX64="build/ios-sim-x64/Release-iphonesimulator/libscanner_core.a"

mkdir -p build/ios-sim-fat
lipo -create "$SARM" "$SX64" -output build/ios-sim-fat/libscanner_core.a

rm -rf ios/Frameworks/scanner_core.xcframework
xcodebuild -create-xcframework \
  -library "$DEV"                              -headers native/include \
  -library build/ios-sim-fat/libscanner_core.a -headers native/include \
  -output ios/Frameworks/scanner_core.xcframework
echo "✅ ios/Frameworks/scanner_core.xcframework তৈরি"
