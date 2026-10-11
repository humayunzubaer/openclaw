import 'package:bangla_translator/bijoy/unicode_to_bijoy.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('unicodeToBijoy', () {
    // Spellings as typed by Bijoy users in SutonnyMJ documents.
    const cases = <String, String>{
      'বাংলাদেশ': 'evsjv‡`k',
      'আমার সোনার বাংলা': 'Avgvi †mvbvi evsjv',
      'গণপ্রজাতন্ত্রী বাংলাদেশ সরকার': 'MYcÖRvZš¿x evsjv‡`k miKvi',
      'জাতীয় রাজস্ব বোর্ড': 'RvZxq ivR¯^ †evW©',
      'মূল্য সংযোজন কর': 'g~j¨ ms‡hvRb Ki',
      'কাস্টমস': 'Kv÷gm',
      'শুল্ক': 'ïé',
      'শুল্কায়ন': 'ïévqb',
      'নিরীক্ষা প্রতিবেদন': 'wbix¶v cÖwZ‡e`b',
      'প্রধানমন্ত্রী': 'cÖavbgš¿x',
      'কর্মকর্তা': 'Kg©KZ©v',
      'কার্যালয়': 'Kvh©vjq',
      'কার্যে': 'Kv‡h©',
      'কীর্তি': 'KxwZ©',
      'সম্পর্কে': 'm¤ú‡K©',
      'বর্তমান': 'eZ©gvb',
      'আন্তর্জাতিক': 'AvšÍR©vwZK',
      'কর্তৃপক্ষ': 'KZ…©c¶',
      'থেকে': '†_‡K',
      'তৈরি': 'ˆZwi',
      'বৌদ্ধ': '†eŠ×',
      'কৌশল': '†KŠkj',
      'ঘোষণা': '†NvlYv',
      'অনুবাদ': 'Abyev`',
      'কুমার': 'Kzgvi',
      'রুশ': 'iæk',
      'দ্রুত': '`ªæZ',
      'হৃদয়': 'ü`q',
      'কৃষি': 'K…wl',
      'গৃহ': 'M„n',
      'স্বাধীনতা': '¯^vaxbZv',
      'ব্যবস্থা': 'e¨e¯’v',
      'ক্ষমতা': '¶gZv',
      'শিক্ষা': 'wk¶v',
      'জ্ঞান': 'Ávb',
      'বিজ্ঞপ্তি': 'weÁwß',
      'চট্টগ্রাম': 'PÆMÖvg',
      'ফ্রান্স': 'd«vÝ',
      'চাঁদ': 'Puv`',
      'অর্থ': 'A_©',
      'পণ্য': 'cY¨',
      'আমদানি': 'Avg`vwb',
      'রপ্তানি': 'ißvwb',
      'ঢাকা': 'XvKv',
      'পড়া': 'cov',
      'বছর ১২৩।': 'eQi 123|',
      'উপ-কমিশনার': 'Dc-Kwgkbvi',
      'প্রেম': '†cÖg',
      'সম্প্রতি': 'm¤cÖwZ',
      'মৃত্যু': 'g„Zz¨',
      'মণ্ডল': 'gÐj',
      'রাষ্ট্রীয়': 'ivóªxq',
      'মন্ত্রণালয়ের নির্দেশনা': 'gš¿Yvj‡qi wb‡`©kbv',
      'সংশ্লিষ্ট কমিশনারেট': 'mswkøó Kwgkbv‡iU',
      'হুকুম': 'ûKzg',
      'কূল': 'K‚j',
      'ঘোড়া': '†Nvov',
      'বৈশাখ': 'ˆekvL',
      'র‍্যাব': 'i¨ve',
      'ক্': 'K&',
      '‘সে’': 'Ô†mÕ',
    };

    cases.forEach((unicode, bijoy) {
      test(unicode, () => expect(unicodeToBijoy(unicode), bijoy));
    });

    test('composed and decomposed nukta letters match', () {
      expect(unicodeToBijoy('য়'), unicodeToBijoy('য়'));
      expect(unicodeToBijoy('ো'), unicodeToBijoy('ো'));
    });
  });

  group('convertToSegments', () {
    test('keeps English words out of SutonnyMJ runs', () {
      expect(convertToSegments('VAT রিটার্ন 2024'), const [
        BijoySegment('VAT ', isBijoy: false),
        BijoySegment('wiUvb©', isBijoy: true),
        BijoySegment(' ', isBijoy: false),
        BijoySegment('2024', isBijoy: true),
      ]);
    });

    test('falls back to Unicode for signs SutonnyMJ cannot draw', () {
      expect(convertToSegments('৳৫০'), const [
        BijoySegment('৳৫০', isBijoy: false),
      ]);
    });

    test('Russian text stays Unicode', () {
      expect(convertToSegments('Привет'), const [
        BijoySegment('Привет', isBijoy: false),
      ]);
    });
  });
}
