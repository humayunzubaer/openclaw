class AppConfig {
  const AppConfig({
    this.assetVersion = 1, // bump করলে model/font আবার provision হবে
    this.ocrScratchBytes = 64 << 20,
    this.eraseScratchBytes = 96 << 20,
    this.tessLang = 'ben',
    this.tessdataAsset = 'assets/tessdata/ben.traineddata',
    this.lamaAsset = 'assets/models/lama_fp16.onnx',
    this.handSegAsset = 'assets/models/handseg_xnnpack.onnx',
    this.bengaliFontAsset = 'assets/fonts/NotoSansBengali-Regular.ttf',
  });
  final int assetVersion;
  final int ocrScratchBytes;
  final int eraseScratchBytes;
  final String tessLang;
  final String tessdataAsset;
  final String lamaAsset;
  final String handSegAsset;
  final String bengaliFontAsset;
}
