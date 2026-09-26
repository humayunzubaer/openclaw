/// বাংলা-ইংরেজি মিশ্র DTP কনভেনশন: সুতন্বী MJ-তে লেখা বাংলার তুলনায় Times New Roman
/// ইংরেজি visually বড় দেখায় — তাই ইংরেজি সবসময় বাংলার চেয়ে ছোট সাইজে বসিয়ে
/// visual ভারসাম্য রাখা হয় (বাংলা ১২pt → ইংরেজি ১০pt, এই ২pt পার্থক্য কনভেনশন)।
class TypesetRule {
  static const String bengaliFont = 'SutonnyMJ'; // SutonnyMjConverter.outputFontFamily-এর সাথে মিলিয়ে ব্যবহার করুন
  static const String englishFont = 'Times New Roman';

  /// ইংরেজি অংশের point size বের করে, বাংলা অংশের size থেকে।
  static double englishSizeFor(double bengaliSizePt, {double deltaPt = 2}) {
    final size = bengaliSizePt - deltaPt;
    return size < 6 ? 6 : size; // অতিরিক্ত ছোট হয়ে অপঠনযোগ্য না হয়ে যায়
  }
}
