from speechready_eval import corpus, metrics


def test_wer_forgives_number_formatting():
    assert metrics.wer("Call five five five, one two three", "Call 555 123") == 0.0
    assert metrics.wer("We sold 1,250 units", "we sold one thousand two hundred fifty units") == 0.0


def test_wer_counts_real_misreads():
    assert metrics.wer("Step one: run npm install", "asterisk asterisk step one asterisk asterisk run npm install") > 0.2


def test_turkish_dotless_i():
    assert metrics.wer("İstanbul güzel", "ISTANBUL GÜZEL", "tr-TR") == 0.0


def test_turkish_acronym_matches_english_letter_names():
    assert metrics.wer("en pi em install çalıştırın.", "NPM install çalıştırın.", "tr-TR") == 0.0
    assert metrics.wer("Adım 1: en pi em install ve si es es dosyası.", "Adım 1: npm install ve CSS dosyası.", "tr-TR") == 0.0
    assert metrics.wer("en pi em install", "ənpeyem instal", "tr-TR") > 0.2  # a real misread stays one


def test_turkish_lone_ordinal_is_how_every_voice_reads_it():
    assert metrics.wer("3. madde önemli.", "Üçüncü madde önemli.", "tr-TR") == 0.0
    assert metrics.wer("Puan 3. Sonra bitti.", "Puan üçüncü, sonra bitti.", "tr-TR") > 0.2  # before a capital it is a cardinal


def test_symbols_the_voices_read_as_words():
    assert metrics.wer("It is 25°C and Acme™ agrees.", "It is 25 degrees Celsius and Acme trademark agrees.") == 0.0
    assert metrics.wer("Meet Berker today &amp; co.", "Meet Berker today & co.") == 0.0
    assert metrics.wer("Hava 25°C.", "Hava 25 derece.", "tr-TR") == 0.0


def test_corpus_builds_from_fixtures():
    lines = corpus.build(("en", "tr"))
    assert len(lines) > 100
    assert any(l.locale == "tr-TR" for l in lines)
    assert all(l.raw and l.intended for l in lines)
