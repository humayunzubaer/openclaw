Pod::Spec.new do |s|
  s.name             = 'scanner_core'
  s.version          = '0.1.0'
  s.summary          = 'Offline Bengali scanner native engine (OpenCV + Tesseract + ONNX).'
  s.platform         = :ios, '14.0'
  s.source           = { :path => '.' }
  s.static_framework = true

  s.vendored_frameworks = [
    'Frameworks/scanner_core.xcframework',
    'Frameworks/opencv2.xcframework',
    'Frameworks/onnxruntime.xcframework',
  ]
  s.vendored_libraries = [
    'Frameworks/libtesseract.a',
    'Frameworks/libleptonica.a',
  ]

  s.frameworks = 'CoreML', 'Accelerate', 'Metal', 'MetalPerformanceShaders'
  s.libraries  = 'c++', 'z'

  # -force_load → FFI symbol dead-strip আটকায়; DynamicLibrary.process() resolve করে।
  s.pod_target_xcconfig = {
    'OTHER_LDFLAGS[sdk=iphoneos*]'        => '-force_load "$(PODS_TARGET_SRCROOT)/Frameworks/scanner_core.xcframework/ios-arm64/libscanner_core.a"',
    'OTHER_LDFLAGS[sdk=iphonesimulator*]' => '-force_load "$(PODS_TARGET_SRCROOT)/Frameworks/scanner_core.xcframework/ios-arm64_x86_64-simulator/libscanner_core.a"',
    'CLANG_CXX_LANGUAGE_STANDARD'         => 'c++17',
  }
end
